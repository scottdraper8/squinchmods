import com.sun.management.HotSpotDiagnosticMXBean;
import java.lang.management.ManagementFactory;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.StandardOpenOption;
import java.util.Arrays;

/** Original bounded HotSpot flag/owned-tmp control, not a filesystem sandbox. */
public class PerfDataFixture {
    public static void main(String[] args) throws Exception {
        String value = ManagementFactory.getPlatformMXBean(HotSpotDiagnosticMXBean.class)
            .getVMOption("UsePerfData").getValue();
        if (!value.equals("false")) throw new AssertionError("UsePerfData=" + value);
        System.out.println("UsePerfData=" + value);
        System.out.println("vmArguments=" + ManagementFactory.getRuntimeMXBean().getInputArguments());
        Path sentinel = Paths.get(System.getProperty("java.io.tmpdir"), "perfdata-disabled-sentinel.txt");
        Files.write(sentinel, "owned scratch only\n".getBytes(StandardCharsets.UTF_8),
            StandardOpenOption.CREATE_NEW, StandardOpenOption.WRITE);
        System.out.println("sentinel=" + sentinel);
        if (args.length != 0) {
            Class.forName(args[0]).getMethod("main", String[].class)
                .invoke(null, (Object) Arrays.copyOfRange(args, 1, args.length));
        }
    }
}
