package com.squinchmods.treeify.common.registry;

import net.minecraft.client.Minecraft;
import net.minecraft.commands.Commands;
import net.minecraft.core.RegistryAccess;
import net.minecraft.server.WorldLoader;
import net.minecraft.server.packs.repository.PackRepository;
import net.minecraft.server.packs.repository.ServerPacksSource;
import net.minecraft.world.flag.FeatureFlags;
import net.minecraft.world.level.DataPackConfig;
import net.minecraft.world.level.WorldDataConfiguration;

import java.util.concurrent.CompletableFuture;

public final class TreeifyResourcePackProvider {

    private TreeifyResourcePackProvider() {
    }

    public static RegistryAccess load() {
        try {
            //? if >= 1.21 {
            PackRepository packRepository = ServerPacksSource.createVanillaTrustedRepository();
            //?} else {
            /*PackRepository packRepository = ServerPacksSource.createPackRepository(java.nio.file.Path.of("dummy"));
            *///?}

            packRepository.reload();

            WorldDataConfiguration worldDataConfiguration = new WorldDataConfiguration(DataPackConfig.DEFAULT, FeatureFlags.DEFAULT_FLAGS);
            
            WorldLoader.PackConfig packConfig = new WorldLoader.PackConfig(packRepository, worldDataConfiguration, false, false);
            
            //? if >= 1.21.11 {
            WorldLoader.InitConfig initConfig = new WorldLoader.InitConfig(packConfig, Commands.CommandSelection.INTEGRATED, net.minecraft.server.permissions.PermissionSet.ALL_PERMISSIONS);
            //?} else {
            /*WorldLoader.InitConfig initConfig = new WorldLoader.InitConfig(packConfig, Commands.CommandSelection.INTEGRATED, 2);
            *///?}

            CompletableFuture<RegistryAccess> future = WorldLoader.load(
                    initConfig,
                    context -> new WorldLoader.DataLoadOutput<>(
                            context.datapackDimensions(),
                            context.datapackDimensions()
                    ),
                    (resources, serverResources, layeredRegistryAccess, data) -> layeredRegistryAccess.compositeAccess(),
                    //? if >= 26.1 {
                    net.minecraft.util.Util.backgroundExecutor(),
                    //?} else if >= 1.21.11 {
                    /*net.minecraft.util.Util.backgroundExecutor(),
                    *///?} else {
                    /*net.minecraft.Util.backgroundExecutor(),
                    *///?}
                    Minecraft.getInstance()
            );

            Minecraft.getInstance().managedBlock(future::isDone);
            return future.get();
        } catch (Exception e) {
            e.printStackTrace();
            return null;
        }
    }
}
