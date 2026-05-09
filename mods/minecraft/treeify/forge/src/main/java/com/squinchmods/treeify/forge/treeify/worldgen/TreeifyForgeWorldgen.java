package com.squinchmods.treeify.forge.treeify.worldgen;

import com.mojang.serialization.Codec;
import com.squinchmods.treeify.common.Treeify;
import net.minecraftforge.common.world.BiomeModifier;
import net.minecraftforge.eventbus.api.IEventBus;
import net.minecraftforge.registries.DeferredRegister;
import net.minecraftforge.registries.ForgeRegistries;
import net.minecraftforge.registries.RegistryObject;

public final class TreeifyForgeWorldgen {

    private static final DeferredRegister<Codec<? extends BiomeModifier>> BIOME_MODIFIER_SERIALIZERS =
            DeferredRegister.create(ForgeRegistries.Keys.BIOME_MODIFIER_SERIALIZERS, Treeify.MOD_ID);

    public static final RegistryObject<Codec<TreeifyBiomeModifier>> TREEIFY_BIOME_MODIFIER =
            BIOME_MODIFIER_SERIALIZERS.register("runtime", () -> Codec.unit(TreeifyBiomeModifier::new));

    public static void register(IEventBus modEventBus) {
        BIOME_MODIFIER_SERIALIZERS.register(modEventBus);
    }

    private TreeifyForgeWorldgen() {
    }
}
