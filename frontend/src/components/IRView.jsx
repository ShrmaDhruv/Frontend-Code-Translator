import { useState } from "react";

function clip(text, max = 70) {
  const flat = String(text).replace(/\s+/g, " ").trim();
  return flat.length > max ? `${flat.slice(0, max)}…` : flat;
}

function Section({ title, items, render }) {
  if (!items || items.length === 0) return null;
  return (
    <section className="detail-section">
      <h3>
        {title} <span className="count">{items.length}</span>
      </h3>
      <ul className="ir-list">
        {items.map((item, index) => {
          const [name, detail] = render(item);
          return (
            <li key={index}>
              <code>{name}</code>
              {detail && <span>{detail}</span>}
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function TemplateNode({ node, depth }) {
  return (
    <>
      <li style={{ paddingLeft: depth * 16 }}>
        {node.tag && <code>&lt;{node.tag}&gt;</code>}
        {node.text && <span className="tpl-text">{clip(node.text, 48)}</span>}
        {node.condition && <span className="badge">if {clip(node.condition, 32)}</span>}
        {node.loop && <span className="badge">for {clip(node.loop, 32)}</span>}
        {(node.events || []).map((binding) => (
          <span className="badge badge-event" key={`${binding.event}-${binding.handler}`}>
            {binding.event} → {clip(binding.handler, 28)}
          </span>
        ))}
      </li>
      {(node.children || []).map((child, index) => (
        <TemplateNode key={index} node={child} depth={depth + 1} />
      ))}
    </>
  );
}

export function IRView({ ir }) {
  const [showJson, setShowJson] = useState(false);

  if (!ir) {
    return <p className="empty">Run a translation to see the intermediate representation.</p>;
  }

  return (
    <div className="detail">
      <div className="detail-bar">
        <p>
          <strong>{ir.component}</strong> extracted from {ir.framework}
        </p>
        <button className="ghost-btn" onClick={() => setShowJson(!showJson)}>
          {showJson ? "Structured" : "JSON"}
        </button>
      </div>

      {showJson ? (
        <pre className="json">{JSON.stringify(ir, null, 2)}</pre>
      ) : (
        <>
          <Section
            title="Props"
            items={ir.props}
            render={(prop) => [prop.name, `${prop.type}${prop.required ? "" : " · optional"}`]}
          />
          <Section
            title="State"
            items={ir.state}
            render={(state) => [state.name, state.init != null ? `= ${clip(state.init)}` : state.type]}
          />
          <Section title="Computed" items={ir.computed} render={(item) => [item.name, clip(item.expression)]} />
          <Section
            title="Methods"
            items={ir.methods}
            render={(method) => [`${method.name}(${(method.params || []).join(", ")})`, clip(method.body)]}
          />
          <Section title="Lifecycle" items={ir.lifecycle} render={(hook) => [hook.hook, clip(hook.body)]} />
          <Section
            title="Imports"
            items={ir.imports}
            render={(item) => [
              item.source,
              [item.default, ...(item.specifiers || [])].filter(Boolean).join(", "),
            ]}
          />
          {ir.template && (
            <section className="detail-section">
              <h3>Template</h3>
              <ul className="tpl-tree">
                <TemplateNode node={ir.template} depth={0} />
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  );
}
