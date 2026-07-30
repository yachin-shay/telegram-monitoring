# Plugins and extension points

## Design intent

The collector writes durable domain events to `plugin_outbox` as part of the
same SQLite transaction as the source record. A plugin must not be required
for collection to succeed.

`OutboxDispatcher` delivers pending events to named callables and records each
successful delivery in `plugin_deliveries`. Delivery is at least once: a crash
after plugin execution but before the delivery marker can cause a repeat.
Plugins should therefore be idempotent.

## Event payload

Message events include:

```json
{
  "account_id": 123,
  "chat_id": -100123,
  "message_id": 456,
  "revision": 0
}
```

The outbox event type identifies the operation. Consumers should query the
database for the complete record rather than assuming the small event payload
contains every field.

## Safe plugin rules

- Never mutate source Telegram data.
- Treat payloads as untrusted input.
- Use bounded network timeouts.
- Make external writes idempotent.
- Keep secrets outside YAML and source control.
- Avoid blocking the daemon event loop; dispatch work to a separate worker if
  the plugin performs slow I/O.
- Record a durable checkpoint in the plugin’s own system if it needs stronger
  exactly-once behavior.

## Current integration status

The outbox schema and dispatcher are implemented, but the foreground daemon
does not currently discover plugin entry points or run a dispatcher loop by
itself. Integrators must wire `OutboxDispatcher` into their process lifecycle
or add that wiring as a follow-up feature.

## Adding a plugin

The current code exposes the dispatcher abstraction rather than a package
discovery convention. A production plugin integration should:

1. Define a callable accepting one event mapping.
2. Register it under a stable plugin name.
3. Run dispatch in a supervised loop.
4. Test duplicate delivery and restart behavior.
5. Keep plugin failure isolated from message persistence.
