"use client";

export default function SettingsPage() {
  return (
    <div className="p-6 space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-sm text-[--color-fg-muted]">
          Most settings live in the .env file at the repo root. UI editing is a future feature.
        </p>
      </header>

      <section className="card text-sm space-y-2">
        <h2 className="text-base font-semibold">Where to configure</h2>
        <p className="text-[--color-fg-muted]">
          To change tokens, the default model, or concurrency, edit <code>.env</code> in the
          installation directory and restart the docker stack.
        </p>
        <pre className="text-xs bg-black/40 p-3 rounded">
{`docker compose down
# edit .env
docker compose up -d`}
        </pre>
      </section>
    </div>
  );
}
