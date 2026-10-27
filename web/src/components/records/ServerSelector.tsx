import { Database, Server } from "lucide-react";

import type { Servidor } from "../../types/api";

interface ServerSelectorProps {
  value: Servidor;
  onChange: (servidor: Servidor) => void;
  disabled?: boolean;
  error?: string;
}

const OPTIONS: Array<{
  value: Servidor;
  number: string;
  title: string;
  subtitle: string;
  detail: string;
  icon: typeof Database;
}> = [
  {
    value: "ubuntu",
    number: "Servidor 1",
    title: "PostgreSQL · Ubuntu",
    subtitle: "api-ubuntu",
    detail: "Paterno opcional. Cadena de integridad api-ubuntu.",
    icon: Database,
  },
  {
    value: "windows",
    number: "Servidor 2",
    title: "SQL Server · Windows",
    subtitle: "api-windows",
    detail: "El apellido paterno es obligatorio en este servidor.",
    icon: Server,
  },
];

export function ServerSelector({ value, onChange, disabled, error }: ServerSelectorProps) {
  return (
    <fieldset
      id="record-servidor"
      className="server-selector"
      aria-describedby={error ? "servidor-error" : "servidor-hint"}
    >
      <legend className="field__label">
        Servidor de destino <span className="field__required">*</span>
      </legend>
      <p id="servidor-hint" className="field__hint">
        Elige un único servidor. El registro no se duplica en el otro.
      </p>
      <div className="server-selector__grid">
        {OPTIONS.map((option) => {
          const Icon = option.icon;
          const selected = value === option.value;
          return (
            <label
              key={option.value}
              className={[
                "server-option",
                selected ? "server-option--selected" : "",
                disabled ? "server-option--disabled" : "",
              ]
                .filter(Boolean)
                .join(" ")}
            >
              <input
                type="radio"
                name="servidor"
                value={option.value}
                checked={selected}
                onChange={() => onChange(option.value)}
                disabled={disabled}
                className="visually-hidden"
              />
              <span className="server-option__icon" aria-hidden="true">
                <Icon size={22} />
              </span>
              <span className="server-option__body">
                <span className="server-option__number">{option.number}</span>
                <strong>{option.title}</strong>
                <span className="small muted">{option.subtitle}</span>
                <span className="server-option__detail">{option.detail}</span>
              </span>
              <span className="server-option__check" aria-hidden="true">
                {selected ? "Seleccionado" : ""}
              </span>
            </label>
          );
        })}
      </div>
      {error ? (
        <p id="servidor-error" className="field__error" role="alert">
          {error}
        </p>
      ) : null}
    </fieldset>
  );
}
