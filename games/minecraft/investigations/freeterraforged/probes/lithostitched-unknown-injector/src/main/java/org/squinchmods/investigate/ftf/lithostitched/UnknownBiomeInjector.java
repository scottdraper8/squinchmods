package org.squinchmods.investigate.ftf.lithostitched;

import java.util.List;
import java.util.Optional;

import com.mojang.serialization.MapCodec;

import dev.worldgen.lithostitched.api.predicate.LoadPredicate;
import dev.worldgen.lithostitched.api.worldgen.biomeinjector.BiomeInjector;
import net.minecraft.core.Holder;
import net.minecraft.resources.ResourceKey;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.dimension.LevelStem;

public enum UnknownBiomeInjector implements BiomeInjector {
	INSTANCE;

	public static final MapCodec<UnknownBiomeInjector> CODEC = MapCodec.unit(INSTANCE);

	@Override
	public Optional<LoadPredicate> predicate() {
		return Optional.empty();
	}

	@Override
	public ResourceKey<LevelStem> dimension() {
		return LevelStem.OVERWORLD;
	}

	@Override
	public int priority() {
		return 0;
	}

	@Override
	public List<Holder<Biome>> possibleBiomes() {
		return List.of();
	}

	@Override
	public MapCodec<? extends BiomeInjector> codec() {
		return CODEC;
	}
}
