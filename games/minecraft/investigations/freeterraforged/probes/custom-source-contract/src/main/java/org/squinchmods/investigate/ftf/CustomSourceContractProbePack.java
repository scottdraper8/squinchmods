package org.squinchmods.investigate.ftf;

import java.util.EnumSet;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.Executors;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicReference;
import java.util.stream.Stream;

import com.google.gson.JsonObject;
import com.mojang.datafixers.util.Pair;
import com.mojang.serialization.MapCodec;

import net.minecraft.core.Holder;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.BiomeSource;
import net.minecraft.world.level.biome.Biomes;
import net.minecraft.world.level.biome.Climate;
import net.minecraft.world.level.dimension.LevelStem;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import etcodehome.freeterraforged.world.worldgen.runtime.BiomeCandidateRoot;
import etcodehome.freeterraforged.world.worldgen.runtime.BiomeSourcePlanInput;
import etcodehome.freeterraforged.world.worldgen.runtime.BiomeSourcePlanInputFactory;
import etcodehome.freeterraforged.world.worldgen.runtime.CapabilityState;
import etcodehome.freeterraforged.world.worldgen.runtime.MinecraftWorldgenPlanCompiler;
import etcodehome.freeterraforged.world.worldgen.runtime.PreviewRequest;
import etcodehome.freeterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenCompilationPurpose;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenFacet;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenPlan;
import etcodehome.freeterraforged.world.worldgen.runtime.WorldgenQueryMode;

public final class CustomSourceContractProbePack implements ProbePack {
	private static final ResourceLocation FACTORY_ID = id("synthetic_custom_source");

	@Override
	public void register() {
		ProbeRegistry.register("squinch:ftf-custom-source-contract", "1", ContractProbe::new);
	}

	private static final class ContractProbe implements ProbeExecution {
		private ContractProbe(ProbeRequest request) {
		}

		@Override
		public ProbeResult tick(MinecraftServer server) throws Exception {
			ServerLevel level = server.overworld();
			if (!(level.getChunkSource().getGenerator() instanceof TerraForgedChunkGenerator active)) {
				JsonObject data = new JsonObject();
				data.addProperty("error", "Selected generator is not the FTF runtime root");
				return ProbeResult.complete(TerminalState.FAIL, ProbePhase.PREDICTION, data, 0);
			}

			Registry<Biome> biomes = level.registryAccess().registryOrThrow(Registries.BIOME);
			Holder<Biome> plains = biomes.getHolderOrThrow(Biomes.PLAINS);
			Holder<Biome> desert = biomes.getHolderOrThrow(Biomes.DESERT);
			AtomicReference<UUID> observedOwner = new AtomicReference<>();
			SyntheticSource factorySource = new SyntheticSource(false, plains, desert, observedOwner);
			PreviewRequest factoryOwner = owner(active, factorySource, "factory");
			WorldgenPlan factoryPlan = compile(factoryOwner);
			BiomeSourcePlanInput factoryInput = factoryPlan.providerSelection().directInput().orElseThrow();
			boolean factoryAcquired = FACTORY_ID.equals(factoryInput.id())
				&& factoryOwner.id().equals(observedOwner.get())
				&& factoryInput.possibleOutputs().equals(Set.of(plains, desert))
				&& factoryInput.resolve(0, 0, 0, null) == plains
				&& factoryInput.resolve(1, 0, 0, null) == desert;

			SyntheticSource malformedSource = new SyntheticSource(true, plains, desert, new AtomicReference<>());
			WorldgenPlan malformedPlan = compile(owner(active, malformedSource, "malformed"));
			boolean malformedBounded = malformedPlan.providerSelection().descriptor().state()
				== CapabilityState.UNAVAILABLE
				&& malformedPlan.providerSelection().descriptor().firstCause()
					.map(failure -> failure.code().equals("custom_source_plan_acquisition_failed"))
					.orElse(false);

			WorldgenPlan opaquePlan = compile(owner(
				active, new OpaqueSource(plains, desert), "opaque"
			));
			boolean opaqueBounded = opaquePlan.biomeComposition().descriptor().state()
				== CapabilityState.UNAVAILABLE
				&& opaquePlan.biomeComposition().descriptor().firstCause()
					.map(failure -> failure.code().equals("source_composition_opaque"))
					.orElse(false);

			BiomeSourcePlanInput directInput = new BiomeSourcePlanInput(
				id("direct_custom_source"), Set.of(plains, desert), WorldgenQueryMode.OWNER_SERIAL,
				(x, y, z, sampler) -> (x & 1) == 0 ? plains : desert
			);
			TerraForgedChunkGenerator directGenerator = new TerraForgedChunkGenerator(
				active.acquisitionBiomeSource(), active.generatorSettings(), Optional.of(directInput)
			);
			WorldgenPlan directPlan = compile(owner(active, directGenerator, "direct"));
			boolean directExclusive = directPlan.providerSelection().directInput().isPresent()
				&& directPlan.providerSelection().providers().isEmpty()
				&& directPlan.biomeComposition().candidateRoot().isEmpty();

			boolean conflictRejected;
			try {
				new TerraForgedChunkGenerator(
					active.acquisitionBiomeSource(), active.generatorSettings(), Optional.of(directInput),
					Optional.of(BiomeCandidateRoot.fromEntries(List.of(
						Pair.of(Climate.parameters(0, 0, 0, 0, 0, 0, 0), plains)
					)))
				);
				conflictRejected = false;
			} catch (IllegalArgumentException expected) {
				conflictRejected = expected.getMessage().contains("mutually exclusive");
			}

			SerialResult serial = exerciseOwnerSerial(directPlan, directInput);
			boolean passed = factoryAcquired && malformedBounded && opaqueBounded
				&& directExclusive && conflictRejected && serial.passed();
			JsonObject data = new JsonObject();
			data.addProperty("factory_acquired", factoryAcquired);
			data.addProperty("factory_owner", String.valueOf(observedOwner.get()));
			data.addProperty("factory_output_count", factoryInput.possibleOutputs().size());
			data.addProperty("malformed_factory_bounded", malformedBounded);
			data.addProperty("malformed_factory_state", malformedPlan.providerSelection().descriptor().state().name());
			data.addProperty("opaque_source_bounded", opaqueBounded);
			data.addProperty("opaque_source_state", opaquePlan.biomeComposition().descriptor().state().name());
			data.addProperty("direct_root_exclusive", directExclusive);
			data.addProperty("direct_candidate_conflict_rejected", conflictRejected);
			data.addProperty("owner_serial_second_blocked", serial.secondBlocked());
			data.addProperty("owner_serial_max_concurrency", serial.maxConcurrency());
			data.addProperty("owner_serial_outputs_correct", serial.outputsCorrect());
			return ProbeResult.complete(
				passed ? TerminalState.PASS : TerminalState.FAIL,
				ProbePhase.PREDICTION,
				data,
				7
			);
		}
	}

	private static SerialResult exerciseOwnerSerial(
		WorldgenPlan plan,
		BiomeSourcePlanInput input
	) throws Exception {
		CountDownLatch firstEntered = new CountDownLatch(1);
		CountDownLatch releaseFirst = new CountDownLatch(1);
		CountDownLatch secondStarted = new CountDownLatch(1);
		CountDownLatch secondEntered = new CountDownLatch(1);
		AtomicInteger active = new AtomicInteger();
		AtomicInteger maximum = new AtomicInteger();
		var workers = Executors.newFixedThreadPool(2);
		Set<WorldgenFacet> facets = EnumSet.of(WorldgenFacet.PROVIDER_SELECTION);
		try {
			var first = workers.submit(() -> plan.execution().execute(facets, () -> {
				int count = active.incrementAndGet();
				maximum.accumulateAndGet(count, Math::max);
				firstEntered.countDown();
				await(releaseFirst);
				try {
					return input.resolve(0, 0, 0, null);
				} finally {
					active.decrementAndGet();
				}
			}));
			if (!firstEntered.await(5, TimeUnit.SECONDS)) {
				throw new IllegalStateException("First owner-serial query did not enter");
			}
			var second = workers.submit(() -> {
				secondStarted.countDown();
				return plan.execution().execute(facets, () -> {
					secondEntered.countDown();
					int count = active.incrementAndGet();
					maximum.accumulateAndGet(count, Math::max);
					try {
						return input.resolve(1, 0, 0, null);
					} finally {
						active.decrementAndGet();
					}
				});
			});
			if (!secondStarted.await(5, TimeUnit.SECONDS)) {
				throw new IllegalStateException("Second owner-serial query did not start");
			}
			boolean secondBlocked = !secondEntered.await(200, TimeUnit.MILLISECONDS);
			releaseFirst.countDown();
			Holder<Biome> firstOutput = first.get(5, TimeUnit.SECONDS);
			Holder<Biome> secondOutput = second.get(5, TimeUnit.SECONDS);
			return new SerialResult(
				secondBlocked,
				maximum.get(),
				firstOutput == input.resolve(0, 0, 0, null)
					&& secondOutput == input.resolve(1, 0, 0, null)
			);
		} finally {
			releaseFirst.countDown();
			workers.shutdownNow();
		}
	}

	private static PreviewRequest owner(
		TerraForgedChunkGenerator active,
		BiomeSource source,
		String identity
	) {
		return owner(
			active,
			new TerraForgedChunkGenerator(source, active.generatorSettings()),
			identity
		);
	}

	private static PreviewRequest owner(
		TerraForgedChunkGenerator active,
		TerraForgedChunkGenerator selected,
		String identity
	) {
		var epoch = active.epoch().orElseThrow();
		return new PreviewRequest(
			UUID.randomUUID(), epoch.dimension(), epoch.seed(), epoch.registries(), epoch.lookups(),
			new LevelStem(epoch.selectedStem().type(), selected), identity,
			epoch.resourceRevision(), epoch.resourceLayerFingerprint(), epoch.tagEpoch(),
			epoch.contributionRevision()
		);
	}

	private static WorldgenPlan compile(PreviewRequest owner) {
		return MinecraftWorldgenPlanCompiler.compile(
			owner, List.of(), WorldgenCompilationPurpose.BIOME_PREVIEW
		);
	}

	private static void await(CountDownLatch latch) {
		try {
			if (!latch.await(5, TimeUnit.SECONDS)) {
				throw new IllegalStateException("Owner-serial query release timed out");
			}
		} catch (InterruptedException failure) {
			Thread.currentThread().interrupt();
			throw new IllegalStateException("Owner-serial query was interrupted", failure);
		}
	}

	private static ResourceLocation id(String path) {
		return ResourceLocation.fromNamespaceAndPath("squinch", path);
	}

	private record SerialResult(
		boolean secondBlocked,
		int maxConcurrency,
		boolean outputsCorrect
	) {
		private boolean passed() {
			return this.secondBlocked && this.maxConcurrency == 1 && this.outputsCorrect;
		}
	}

	private static final class SyntheticSource extends BiomeSource implements BiomeSourcePlanInputFactory {
		private static final MapCodec<SyntheticSource> CODEC = MapCodec.unit(() -> null);
		private final boolean malformed;
		private final Holder<Biome> first;
		private final Holder<Biome> second;
		private final AtomicReference<UUID> observedOwner;

		private SyntheticSource(
			boolean malformed,
			Holder<Biome> first,
			Holder<Biome> second,
			AtomicReference<UUID> observedOwner
		) {
			this.malformed = malformed;
			this.first = first;
			this.second = second;
			this.observedOwner = observedOwner;
		}

		@Override
		public ResourceLocation biomeSourcePlanFactoryId() {
			return FACTORY_ID;
		}

		@Override
		public BiomeSourcePlanInput createBiomeSourcePlanInput(
			etcodehome.freeterraforged.world.worldgen.runtime.WorldgenOwner owner
		) {
			this.observedOwner.set(owner.id());
			return new BiomeSourcePlanInput(
				this.malformed ? id("wrong_factory") : FACTORY_ID,
				Set.of(this.first, this.second),
				WorldgenQueryMode.OWNER_SERIAL,
				(x, y, z, sampler) -> (x & 1) == 0 ? this.first : this.second
			);
		}

		@Override
		protected MapCodec<? extends BiomeSource> codec() {
			return CODEC;
		}

		@Override
		protected Stream<Holder<Biome>> collectPossibleBiomes() {
			return Stream.of(this.first, this.second);
		}

		@Override
		public Holder<Biome> getNoiseBiome(int x, int y, int z, Climate.Sampler sampler) {
			return (x & 1) == 0 ? this.first : this.second;
		}
	}

	private static final class OpaqueSource extends BiomeSource {
		private static final MapCodec<OpaqueSource> CODEC = MapCodec.unit(() -> null);
		private final Holder<Biome> first;
		private final Holder<Biome> second;

		private OpaqueSource(Holder<Biome> first, Holder<Biome> second) {
			this.first = first;
			this.second = second;
		}

		@Override
		protected MapCodec<? extends BiomeSource> codec() {
			return CODEC;
		}

		@Override
		protected Stream<Holder<Biome>> collectPossibleBiomes() {
			return Stream.of(this.first, this.second);
		}

		@Override
		public Holder<Biome> getNoiseBiome(int x, int y, int z, Climate.Sampler sampler) {
			return (x & 1) == 0 ? this.first : this.second;
		}
	}
}
