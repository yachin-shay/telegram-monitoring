import asyncio
import json
import queue

from telegram_osint.tdlib import Authorization, TdJsonClient


class FakeNative:
    def __init__(self) -> None:
        self.sent: list[dict[str, object]] = []
        self.incoming: queue.Queue[bytes] = queue.Queue()

    def send(self, request: bytes) -> None:
        self.sent.append(json.loads(request))

    def receive(self, timeout: float) -> bytes | None:
        try:
            return self.incoming.get(timeout=min(timeout, 0.01))
        except queue.Empty:
            return None

    def execute(self, request: bytes) -> bytes:
        return b'{"@type":"text","text":"1.8.0"}'


def test_tdlib_correlates_responses_and_delivers_updates_in_order() -> None:
    async def scenario() -> None:
        native = FakeNative()
        updates: list[str] = []
        client = TdJsonClient(native=native, update_handler=lambda item: updates.append(item["@type"]))
        await client.start()
        try:
            pending = asyncio.create_task(client.request({"@type": "getMe"}))
            await asyncio.sleep(0.01)
            correlation = native.sent[0]["@extra"]
            native.incoming.put(b'{"@type":"updateUser","user":{"id":"1"}}')
            native.incoming.put(
                json.dumps({"@type": "user", "id": "1", "@extra": correlation}).encode()
            )
            response = await asyncio.wait_for(pending, timeout=1)
            await asyncio.sleep(0.02)
            assert response["id"] == "1"
            assert updates == ["updateUser"]
        finally:
            await client.close()

    asyncio.run(scenario())


def test_authorization_translates_tdlib_states_to_supported_requests() -> None:
    requests: list[dict[str, object]] = []
    auth = Authorization(
        send=requests.append,
        api_id=123,
        api_hash="hash",
        database_directory="/state/tdlib",
        files_directory="/state/files",
    )

    auth.handle({"@type": "authorizationStateWaitTdlibParameters"})
    auth.handle({"@type": "authorizationStateWaitPhoneNumber"})
    auth.request_qr()
    auth.submit_phone("+12025550123")
    auth.handle({"@type": "authorizationStateWaitCode"})
    auth.submit_code("12345")

    assert requests[0]["@type"] == "setTdlibParameters"
    assert requests[1]["@type"] == "requestQrCodeAuthentication"
    assert requests[2] == {
        "@type": "setAuthenticationPhoneNumber",
        "phone_number": "+12025550123",
    }
    assert requests[3] == {"@type": "checkAuthenticationCode", "code": "12345"}
