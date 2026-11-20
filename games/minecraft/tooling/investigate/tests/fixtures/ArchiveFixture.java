import java.lang.instrument.Instrumentation;

/** Original startup-recipe control, never a game or production probe. */
public class ArchiveFixture {
    public static void main(String[] args) throws Exception {
        try {
            Class<?> payload = Class.forName("ArchivePayload");
            System.out.println("payload=" + payload.getMethod("value").invoke(null));
            System.out.println("bootstrap=" + (payload.getClassLoader() == null));
        } catch (ClassNotFoundException absent) {
            System.out.println("payload=absent");
        }
        System.out.println("agent=" + System.getProperty("archive.agent", "absent"));
        if (args.length == 1 && args[0].equals("vm-maps")) {
            for (String line : java.nio.file.Files.readAllLines(java.nio.file.Paths.get("/proc/self/maps"))) {
                if (line.contains("libjvm.so")) System.out.println(line);
            }
        }
    }

    public static class Agent {
        public static void premain(String options, Instrumentation instrumentation) throws Exception {
            agentmain(options, instrumentation);
        }
        public static void agentmain(String options, Instrumentation instrumentation) throws Exception {
            Class<?> payload = Class.forName("ArchivePayload");
            System.setProperty("archive.agent", (String) payload.getMethod("value").invoke(null));
        }
    }
}
