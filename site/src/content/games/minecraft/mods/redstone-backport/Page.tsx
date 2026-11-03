import { redstoneBackport } from "./mod";

export function RedstoneBackportPage() {
  return (
    <main>
      <h1>{redstoneBackport.name}</h1>
      <p>For Minecraft Java Edition 1.20.1. Available for Fabric, Quilt, and Forge.</p>
      <ul>
        <li>
          <strong>/tick command (from Minecraft 1.20.3):</strong> Freeze, step, sprint, and control
          the server tick rate.
        </li>
        <li>
          <strong>Crafter (from Minecraft 1.21):</strong> Automate crafting with redstone pulses,
          disabled slots, and hopper or dropper input.
        </li>
        <li>
          <strong>Witch redstone drops (from Minecraft 1.21):</strong> Witches drop 4–8 redstone
          dust, with Looting affecting the amount.
        </li>
      </ul>
    </main>
  );
}
