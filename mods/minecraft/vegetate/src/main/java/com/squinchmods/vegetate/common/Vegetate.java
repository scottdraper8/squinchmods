package com.squinchmods.vegetate.common;

import com.squinchmods.vegetate.common.vegetate.rules.VegetateConfigService;
import net.minecraft.resources.ResourceLocation;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class Vegetate {
  public static final String MOD_ID = "vegetate";
  private static final Logger LOGGER = LoggerFactory.getLogger(Vegetate.MOD_ID);
  private static final VegetateConfigService CONFIG_SERVICE = new VegetateConfigService();

  public static VegetateConfigService getConfigService() {
    return CONFIG_SERVICE;
  }

  public static Logger getLogger() {
    return LOGGER;
  }

  public static ResourceLocation makeId(String path) {
    return ResourceLocation.fromNamespaceAndPath(MOD_ID, path);
  }

  public static void init() {
    CONFIG_SERVICE.create();
    CONFIG_SERVICE.load();
  }
}
