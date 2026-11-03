import { generousGiver } from "./mod";

export function GenerousGiverPage() {
  return (
    <main>
      <h1>{generousGiver.name}</h1>
      <p>
        Choose to offer 5, 10, 15, or 20 gifts to an alien in one interaction, and choose whether to
        keep the dialogue open afterward.
      </p>
    </main>
  );
}
