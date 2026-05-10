package com.squinchmods.vegetate.forge.vegetate.worldgen;

import com.mojang.serialization.Codec;
import com.squinchmods.vegetate.common.Vegetate;
import net.minecraftforge.common.world.BiomeModifier;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class VegetateForgeWorldgen {

  private static final DeferredRegister<Codec<? extends BiomeModifier>> BIOME_MODIFIER_SERIALIZERS =
      DeferredRegister.create(ForgeRegistries.Keys.BIOME_MODIFIER_SERIALIZERS, Vegetate.MOD_ID);

  public static final RegistryObject<Codec<VegetateBiomeModifier>> VEGETATE_BIOME_MODIFIER =
      BIOME_MODIFIER_SERIALIZERS.register("runtime", () -> Codec.unit(VegetateBiomeModifier::new));

  public static void register(IEventBus modEventBus) {
    BIOME_MODIFIER_SERIALIZERS.register(modEventBus);
  }

  private VegetateForgeWorldgen() {}
}
