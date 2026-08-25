import Config

# We don't run a server during test. If one is required,
# you can enable the server option below.
config :air_monitor_web, AirMonitorWeb.Endpoint,
  http: [ip: {127, 0, 0, 1}, port: 4002],
  secret_key_base: "GFZRk160FHrtT03dPRknt3kc1x4rLfRWufd6Klixf28zYy8T68kmBy6RPpbqe3ZE",
  server: false
