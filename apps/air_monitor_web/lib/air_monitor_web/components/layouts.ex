defmodule AirMonitorWeb.Layouts do
  use AirMonitorWeb, :html

  def root(assigns) do
    ~H"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <meta name="csrf-token" content={get_csrf_token()} />
        <title>Air Monitor</title>
        <style>
          body { margin: 0; padding: 2rem; background: #f5f7fa; color: #172033; font-family: system-ui, sans-serif; }
          main { max-width: 1200px; margin: 0 auto; }
          #charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; }
          .chart { padding: 1rem; border: 1px solid #dce2ea; border-radius: 8px; background: white; }
          .summary { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; margin-bottom: 1rem; }
          .latest-value { font-size: 1.5rem; font-weight: 700; }
          .status { color: #64748b; }
          svg { display: block; width: 100%; height: auto; }
        </style>
        <script type="importmap">
          {
            "imports": {
              "phoenix": "/vendor/phoenix/phoenix.mjs",
              "phoenix_live_view": "/vendor/phoenix_live_view/phoenix_live_view.esm.js"
            }
          }
        </script>
        <script type="module">
          import {Socket} from "phoenix"
          import {LiveSocket} from "phoenix_live_view"

          const csrfToken = document.querySelector("meta[name='csrf-token']").getAttribute("content")
          const liveSocket = new LiveSocket("/live", Socket, {params: {_csrf_token: csrfToken}})
          liveSocket.connect()
          window.liveSocket = liveSocket
        </script>
      </head>
      <body>
        {@inner_content}
      </body>
    </html>
    """
  end
end
