export function AboutPage() {
  return (
    <section className="page">
      <h1>About KrushiBandhu AI</h1>
      <p className="lead">
        KrushiBandhu helps farmers combine local farm boundaries, weather trends, and AI predictions to make better
        crop planning decisions.
      </p>

      <div className="grid">
        <article className="card">
          <h3>What this app does</h3>
          <p>Stores farm boundaries, runs district-level crop yield prediction, and prepares future agronomy modules.</p>
        </article>
        <article className="card">
          <h3>Tech stack</h3>
          <p>Frontend in React + Vite and backend in FastAPI with MySQL (`krushibandu_ai`) for persistent storage.</p>
        </article>
        <article className="card">
          <h3>Current model endpoints</h3>
          <p>`/predict-advanced`, `/optimize-yield`, `/optimize-soil`, plus farm APIs such as `/my-farm`.</p>
        </article>
      </div>
    </section>
  );
}
