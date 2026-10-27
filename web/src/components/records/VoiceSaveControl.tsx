import { useState } from "react";

import { AudioLines, Mic, MicOff, TriangleAlert } from "lucide-react";

import { useSpeechRecognition } from "../../hooks/useSpeechRecognition";
import type { Servidor } from "../../types/api";
import { parseVoiceCommand } from "../../utils/voiceCommands";
import { Alert } from "../ui/Alert";
import { Button } from "../ui/Button";

interface VoiceSaveControlProps {
  disabled?: boolean;
  onSaveRequested: (servidor: Servidor | null, rawText: string) => string;
}

export function VoiceSaveControl({ disabled, onSaveRequested }: VoiceSaveControlProps) {
  const [message, setMessage] = useState<string | null>(null);
  const [messageTone, setMessageTone] = useState<"info" | "warning">("info");

  const { supported, listening, interim, error, start, stop, clearError } =
    useSpeechRecognition((text) => {
      const command = parseVoiceCommand(text);
      if (command.type === "unknown") {
        setMessageTone("warning");
        setMessage(
          `No reconocí un comando para guardar. Di, por ejemplo: “Guardar en servidor 1” o “Guardar en Windows”. Escuché: “${text}”.`,
        );
        return;
      }
      setMessageTone("info");
      setMessage(onSaveRequested(command.servidor, command.text));
    });

  if (!supported) {
    return (
      <Alert tone="neutral" title="Reconocimiento de voz no disponible">
        Este navegador no ofrece Web Speech API. Puedes elegir el servidor y guardar con
        los botones del formulario. Los comandos de voz solo se usan para guardar
        registros.
      </Alert>
    );
  }

  return (
    <div className="voice-save">
      <div className="voice-save__header">
        <div>
          <p className="voice-save__title">
            <AudioLines aria-hidden="true" size={18} /> Guardar por voz
          </p>
          <p className="small muted">
            Di “Guardar en servidor 1” (Ubuntu), “Guardar en servidor 2” (Windows) o
            “Guardar en Ubuntu/Windows”. Después revisarás y confirmarás el envío.
          </p>
        </div>
        <Button
          variant={listening ? "danger" : "secondary"}
          size="sm"
          onClick={() => {
            clearError();
            setMessage(null);
            if (listening) stop();
            else start();
          }}
          disabled={disabled}
          icon={
            listening ? (
              <MicOff aria-hidden="true" size={17} />
            ) : (
              <Mic aria-hidden="true" size={17} />
            )
          }
          aria-pressed={listening}
        >
          {listening ? "Detener escucha" : "Dictar comando"}
        </Button>
      </div>

      {listening ? (
        <p className="voice-save__listening" role="status" aria-live="polite">
          <span className="listening-dot" aria-hidden="true" />
          Escuchando… {interim ? `“${interim}”` : "habla ahora"}
        </p>
      ) : null}

      {error ? (
        <Alert tone="warning" title="No se pudo usar el micrófono">
          {error}
        </Alert>
      ) : null}

      {message ? (
        <Alert
          tone={messageTone === "warning" ? "warning" : "info"}
          title={messageTone === "warning" ? "Comando no aplicado" : "Comando reconocido"}
          live
        >
          {message}
        </Alert>
      ) : null}

      <p className="voice-save__hint small">
        <TriangleAlert aria-hidden="true" size={14} /> El micrófono se detiene
        automáticamente. Esta función no consulta el clima.
      </p>
    </div>
  );
}
