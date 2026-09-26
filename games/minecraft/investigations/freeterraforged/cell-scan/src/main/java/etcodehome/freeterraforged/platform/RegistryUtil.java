package etcodehome.freeterraforged.platform;

import java.util.List;

import com.mojang.serialization.Codec;
import com.mojang.serialization.Lifecycle;

import net.minecraft.core.MappedRegistry;
import net.minecraft.core.Registry;
import net.minecraft.resources.RegistryDataLoader;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.GameRules;
import etcodehome.freeterraforged.FTFCommon;

/**
 * Standalone replacement for FTF's loader-injected platform bridge. Cell scanning needs only plain
 * in-memory registries; it deliberately does not register Fabric/NeoForge synced registries or
 * game rules because no loader or game instance exists in this process.
 */
public final class RegistryUtil {
    private RegistryUtil() {
    }

    public static <T> void register(Registry<T> registry, String name, T value) {
        Registry.register(registry, FTFCommon.location(name), value);
    }

    public static <T> Registry<T> createRegistry(ResourceKey<Registry<T>> key) {
        return new MappedRegistry<>(key, Lifecycle.stable());
    }

    public static <T> void createDataRegistry(
        ResourceKey<Registry<T>> key, Codec<T> codec, boolean synced
    ) {
        // Dynamic datapack registration belongs to a loader lifecycle and is not needed here.
    }

    public static <T extends GameRules.Value<T>> GameRules.Key<T> registerGameRule(
        String name, GameRules.Category category, GameRules.Type<T> type
    ) {
        throw new UnsupportedOperationException("game rules are outside standalone cell scanning");
    }

    public static List<RegistryDataLoader.RegistryData<?>> getDynamicRegistries() {
        return List.of();
    }

    public static List<RegistryDataLoader.RegistryData<?>> getDynamicRegistriesWithDimensions() {
        return RegistryDataLoader.DIMENSION_REGISTRIES;
    }
}
