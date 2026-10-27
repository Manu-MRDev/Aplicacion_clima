import { describe, expect, it } from "vitest";

import { parseVoiceCommand } from "../utils/voiceCommands";

describe("parseVoiceCommand", () => {
  it.each([
    ["guardar en servidor 1", "ubuntu"],
    ["Guarda en el servidor uno", "ubuntu"],
    ["guardar en ubuntu", "ubuntu"],
    ["guardar en PostgreSQL", "ubuntu"],
    ["guardar en servidor 2", "windows"],
    ["guarda en el servidor dos", "windows"],
    ["guardar en Windows", "windows"],
    ["guardar en SQL Server", "windows"],
  ])("interpreta %s", (text, expected) => {
    const command = parseVoiceCommand(text);
    expect(command.type).toBe("save");
    if (command.type === "save") {
      expect(command.servidor).toBe(expected);
    }
  });

  it("usa el servidor ya seleccionado si no se indica uno", () => {
    const command = parseVoiceCommand("guardar registro");
    expect(command).toEqual({
      type: "save",
      servidor: null,
      text: "guardar registro",
    });
  });

  it("no adivina cuando se mencionan ambos servidores", () => {
    const command = parseVoiceCommand("guardar en servidor 1 o 2");
    expect(command.type).toBe("unknown");
  });

  it("rechaza comandos que no son de guardado", () => {
    expect(parseVoiceCommand("consultar el clima").type).toBe("unknown");
    expect(parseVoiceCommand("actualizar el clima").type).toBe("unknown");
    expect(parseVoiceCommand("usar mi ubicación").type).toBe("unknown");
  });
});
