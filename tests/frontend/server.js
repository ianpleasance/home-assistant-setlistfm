import { createServer } from "node:http";
import { readFile } from "node:fs/promises";

const files = new Map([
  ["/", [new URL("./fixture.html", import.meta.url), "text/html"]],
  ["/setlistfm-cards.js", [new URL("../../custom_components/setlistfm/www/setlistfm-cards.js", import.meta.url), "text/javascript"]],
]);
createServer(async (request, response) => {
  const file = files.get(new URL(request.url, "http://localhost").pathname);
  if (!file) { response.writeHead(404).end(); return; }
  try {
    const data = await readFile(file[0]);
    response.writeHead(200, { "Content-Type": file[1], "Cache-Control": "no-store" }).end(data);
  } catch (error) {
    console.error(error);
    response.writeHead(500).end("Fixture could not be loaded");
  }
}).listen(18763, "127.0.0.1");
