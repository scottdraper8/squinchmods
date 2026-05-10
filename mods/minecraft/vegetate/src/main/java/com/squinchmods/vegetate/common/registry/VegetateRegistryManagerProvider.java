package com.squinchmods.vegetate.common.registry;

import net.minecraft.core.RegistryAccess;
import org.jetbrains.annotations.Nullable;

/**
 * Provides access to the Minecraft {@link RegistryAccess} instance.
 */
public final class VegetateRegistryManagerProvider {

    private static RegistryAccess registryManager;
    private static RegistryAccess catalogRegistryManager;

    public static void setRegistryManager(RegistryAccess registryAccess) {
        registryManager = registryAccess;
    }

    @Nullable
    public static RegistryAccess getRegistryManager() {
        return registryManager;
    }

    @Nullable
    public static RegistryAccess getOrLoadRegistryManager() {
        if (registryManager != null) {
            return registryManager;
        }

        registryManager = VegetateResourcePackProvider.load();
        return registryManager;
    }

    @Nullable
    public static RegistryAccess getOrLoadCatalogRegistryManager() {
        if (catalogRegistryManager != null) {
            return catalogRegistryManager;
        }

        catalogRegistryManager = VegetateResourcePackProvider.load();
        return catalogRegistryManager;
    }

    private VegetateRegistryManagerProvider() {
    }
}
