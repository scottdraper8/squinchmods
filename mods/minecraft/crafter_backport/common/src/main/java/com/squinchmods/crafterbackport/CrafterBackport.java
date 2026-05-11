package com.squinchmods.crafterbackport;

import com.mojang.logging.LogUtils;
import net.minecraft.resources.ResourceLocation;
import org.slf4j.Logger;

public class CrafterBackport {
  public static final String MOD_ID = "crafter_backport";
  public static final Logger LOGGER = LogUtils.getLogger();

  public static ResourceLocation id(String path) {
    return new ResourceLocation(MOD_ID, path);
  }
}
