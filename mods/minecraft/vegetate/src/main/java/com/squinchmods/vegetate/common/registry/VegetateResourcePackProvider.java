package com.squinchmods.vegetate.common.registry;

import java.nio.file.Path;
import java.util.concurrent.CompletableFuture;
import net.minecraft.Util;
import net.minecraft.client.Minecraft;
import net.minecraft.commands.Commands;
import net.minecraft.core.RegistryAccess;
import net.minecraft.server.WorldLoader;
import net.minecraft.server.packs.repository.PackRepository;
import net.minecraft.server.packs.repository.ServerPacksSource;
import net.minecraft.world.flag.FeatureFlags;
import net.minecraft.world.level.DataPackConfig;
import net.minecraft.world.level.WorldDataConfiguration;
import org.jetbrains.annotations.Nullable;

public final class VegetateResourcePackProvider {

  private VegetateResourcePackProvider() {}

  public static @Nullable RegistryAccess load() {
    try {
      PackRepository packRepository = ServerPacksSource.createPackRepository(Path.of("dummy"));
      packRepository.reload();

      WorldDataConfiguration worldDataConfiguration =
          new WorldDataConfiguration(DataPackConfig.DEFAULT, FeatureFlags.DEFAULT_FLAGS);
      WorldLoader.PackConfig packConfig =
          new WorldLoader.PackConfig(packRepository, worldDataConfiguration, false, false);
      WorldLoader.InitConfig initConfig =
          new WorldLoader.InitConfig(packConfig, Commands.CommandSelection.INTEGRATED, 2);

      CompletableFuture<RegistryAccess> future =
          WorldLoader.load(
              initConfig,
              context ->
                  new WorldLoader.DataLoadOutput<>(
                      context.datapackDimensions(), context.datapackDimensions()),
              (resources, serverResources, layeredRegistryAccess, data) ->
                  layeredRegistryAccess.compositeAccess(),
              Util.backgroundExecutor(),
              Minecraft.getInstance());

      Minecraft.getInstance().managedBlock(future::isDone);
      return future.get();
    } catch (Exception e) {
      e.printStackTrace();
      return null;
    }
  }
}
