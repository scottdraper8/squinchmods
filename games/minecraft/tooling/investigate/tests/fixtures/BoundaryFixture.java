import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Paths;

/** Original launcher fixture, not Minecraft, a loader, or a production probe. */
public class BoundaryFixture {
    public static void main(String[] args) throws Exception {
        if (args.length != 2 || !args[0].equals("@missing") || !args[1].equals("@app.data")) {
            throw new AssertionError("Literal application arguments changed");
        }
        Files.write(Paths.get(args[1].substring(1)), "application-mutated\n".getBytes(StandardCharsets.UTF_8));
        System.out.println("[\"@missing\",\"@app.data\"]");
    }
}
