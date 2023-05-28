from blockwork.containers import Foundation

container = Foundation()
container.set("TEST", "VALUE_123")

# Launch an interactive shell
container.shell()

# Run a command
container.launch("echo", "hi")
