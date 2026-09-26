import { redstoneBackport } from "./mod";

import "./styles.scss";

export function RedstoneBackportOverview() {
  return (
    <div className="redstone-overview">
      <div className="mod-facts" aria-label="Mod details">
        <span>{redstoneBackport.status}</span>
        <span>Minecraft Java {redstoneBackport.minecraftVersion}</span>
        <span>{redstoneBackport.loaders.join(" · ")}</span>
      </div>

      <section aria-labelledby="redstone-features-title">
        <div className="section-heading">
          <p className="eyebrow">WHAT'S INSIDE</p>
          <h2 id="redstone-features-title">Redstone, updated.</h2>
        </div>
        <div className="feature-grid">
          {redstoneBackport.features.map((feature) => (
            <article className="feature-card" key={feature.title}>
              <span className="feature-source">From Minecraft {feature.sourceVersion}</span>
              <h3>{feature.title}</h3>
              <p>{feature.detail}</p>
            </article>
          ))}
        </div>
      </section>

      <footer className="mod-attribution">
        <span>License: {redstoneBackport.license}</span>
        <a href={redstoneBackport.repository}>View project source ↗</a>
      </footer>
    </div>
  );
}
