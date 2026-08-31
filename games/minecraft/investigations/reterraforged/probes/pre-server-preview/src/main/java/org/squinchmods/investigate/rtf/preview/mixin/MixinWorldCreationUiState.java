package org.squinchmods.investigate.rtf.preview.mixin;

import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import java.util.Map;
import java.util.OptionalLong;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicBoolean;

import com.google.gson.JsonObject;
import com.mojang.serialization.JsonOps;

import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screens.worldselection.WorldCreationContext;
import net.minecraft.client.gui.screens.worldselection.WorldCreationUiState;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderLookup;
import net.minecraft.core.RegistryAccess;
import net.minecraft.resources.ResourceKey;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.level.biome.Biome;
import net.minecraft.world.level.biome.MultiNoiseBiomeSource;
import net.minecraft.world.level.dimension.LevelStem;
import net.minecraft.world.level.levelgen.NoiseBasedChunkGenerator;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import raccoonman.reterraforged.world.worldgen.runtime.MinecraftWorldgenPlanCompiler;
import raccoonman.reterraforged.world.worldgen.runtime.MinecraftBiomeSourceGraphs;
import raccoonman.reterraforged.world.worldgen.runtime.PreviewRequest;
import raccoonman.reterraforged.world.worldgen.runtime.PreviewSourceContext;
import raccoonman.reterraforged.world.worldgen.runtime.PreviewSourceNegotiator;
import raccoonman.reterraforged.world.worldgen.runtime.TagEpoch;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenBiomeSelection;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenCapabilityDiscovery;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenCompilationPurpose;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenFingerprints;
import raccoonman.reterraforged.world.worldgen.runtime.PreServerWorldgenContext;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPreServerFinalizer;
import raccoonman.reterraforged.data.worldgen.preset.settings.Preset;
import raccoonman.reterraforged.data.worldgen.preset.settings.Presets;
import raccoonman.reterraforged.registries.RTFRegistries;
import raccoonman.reterraforged.world.worldgen.GeneratorContext;
import raccoonman.reterraforged.world.worldgen.biome.BiomePreviewResolver;
import org.spongepowered.asm.mixin.Shadow;

@Mixin(WorldCreationUiState.class)
public abstract class MixinWorldCreationUiState {
	private static final AtomicBoolean SQUINCH_CAPTURED = new AtomicBoolean();
	@Shadow
	private WorldCreationContext settings;

	@Inject(method = "<init>", at = @At("TAIL"))
	private void squinch$compileInitialPreServerPreview(CallbackInfo callback) {
		this.squinch$compilePreServerPreview(this.settings);
	}

	@Inject(method = "setSettings", at = @At("TAIL"))
	private void squinch$compileUpdatedPreServerPreview(WorldCreationContext context, CallbackInfo callback) {
		this.squinch$compilePreServerPreview(context);
	}

	private void squinch$compilePreServerPreview(WorldCreationContext context) {
		String configuredSeed = System.getenv("SQUINCH_PREVIEW_SEED");
		if (configuredSeed != null && !configuredSeed.isBlank()) {
			long seed = Long.parseLong(configuredSeed);
			context = context.withOptions(options -> options.withSeed(OptionalLong.of(seed)));
		}
		LevelStem selected = context.selectedDimensions().get(LevelStem.OVERWORLD).orElse(null);
		if (selected == null
			|| !(selected.generator() instanceof NoiseBasedChunkGenerator)
			|| !SQUINCH_CAPTURED.compareAndSet(false, true)) {
			return;
		}
		WorldgenPreServerFinalizer.finalize(new PreServerWorldgenContext(
			context.worldgenLoadContext(), context.selectedDimensions(), context.options().seed()
		));

		JsonObject result = new JsonObject();
		result.addProperty("world_creation_context", context.getClass().getName());
		result.addProperty("server_present", Minecraft.getInstance().getSingleplayerServer() != null);
		result.addProperty("selected_source", selected.generator().getBiomeSource().getClass().getName());
		result.addProperty("selected_terraforged_generator", selected.generator() instanceof TerraForgedChunkGenerator);
		PreviewSourceNegotiator.Result sourceResult = null;
		try {
			if (!(selected.generator() instanceof NoiseBasedChunkGenerator noiseGenerator)) {
				throw new IllegalStateException("selected generator is not noise based");
			}
			long seed = context.options().seed();
			String tags = WorldgenFingerprints.tags(context.worldgenLoadContext());
			var providers = WorldgenCapabilityDiscovery.discover(getClass().getClassLoader());
			sourceResult = PreviewSourceNegotiator.resolve(
				new PreviewSourceContext(
					seed,
					context.worldgenLoadContext(),
					context.worldgenLoadContext(),
					MinecraftBiomeSourceGraphs.acquisitionSource(selected.generator()),
					noiseGenerator.generatorSettings(),
					"world_creation_context",
					context.dataConfiguration().toString(),
					new TagEpoch(0L, tags)
				),
				providers
			);
			TerraForgedChunkGenerator previewGenerator = new TerraForgedChunkGenerator(
				sourceResult.owned().source(), noiseGenerator.generatorSettings()
			);
			PreviewRequest request = PreviewRequest.create(
				LevelStem.OVERWORLD,
				seed,
				context.worldgenLoadContext(),
				context.worldgenLoadContext(),
				new LevelStem(selected.type(), previewGenerator),
				"world_creation_context",
				context.dataConfiguration().toString(),
				new TagEpoch(0L, tags)
			);
			var plan = MinecraftWorldgenPlanCompiler.compile(
				request, providers, WorldgenCompilationPurpose.BIOME_PREVIEW
			);
			WorldgenBiomeSelection.requireExecutablePlan(plan);
			RegistryAccess.Frozen registries = context.worldgenLoadContext();
			Preset requestedPreset = Presets.makeRTFDefault();
			HolderLookup.Provider previewLookups = requestedPreset.buildPreviewLookups(registries);
			Preset preparedPreset = previewLookups.lookupOrThrow(RTFRegistries.PRESET)
				.getOrThrow(Preset.KEY).value();
			result.add("preset", Preset.DIRECT_CODEC.encodeStart(JsonOps.INSTANCE, preparedPreset).getOrThrow());
			GeneratorContext generatorContext = GeneratorContext.makeUncached(
				preparedPreset,
				previewLookups.lookupOrThrow(RTFRegistries.NOISE),
				(int) seed,
				4,
				0,
				6
			);
			Map<String, Integer> palette = new TreeMap<>();
			MessageDigest gridDigest = sha256();
			try (
				BiomePreviewResolver resolver = BiomePreviewResolver.create(
					registries,
					previewLookups,
					LevelStem.OVERWORLD,
					selected.type(),
					selected.generator(),
					preparedPreset,
					generatorContext,
					seed,
					"world_creation_context",
					context.dataConfiguration().toString(),
					tags
				);
				var tile = generatorContext.generator.generateZoomed(0, 0, 64, true, () -> false).join()
			) {
				BiomePreviewResolver.ResolvedTile resolved = resolver.resolveSurfaceTile(
					tile, 0, 0, 64, generatorContext.levels, () -> false
				);
				for (int z = 0; z < resolved.size(); z++) {
					for (int x = 0; x < resolved.size(); x++) {
						String id = resolved.biomeAt(x, z).unwrapKey()
							.map(ResourceKey::location)
							.map(ResourceLocation::toString)
							.orElse("unregistered");
						palette.merge(id, 1, Integer::sum);
						gridDigest.update(id.getBytes(StandardCharsets.UTF_8));
						gridDigest.update((byte) 0);
					}
				}
				JsonObject candidateDomains = new JsonObject();
				resolver.plan().providerSelection().providers().forEach(domain ->
					candidateDomains.addProperty(domain.id().toString(), domain.candidates().values().size())
				);
				result.add("candidate_domains", candidateDomains);
				result.addProperty(
					"root_composition_domain",
					resolver.plan().providerSelection().rootCompositionDomain().orElseThrow().toString()
				);
				result.addProperty("composition_entry_count", resolver.plan().biomeComposition().entries().size());
				result.addProperty("contribution_sequence", resolver.plan().owner().contributionSequence());
			}
			JsonObject paletteJson = new JsonObject();
			palette.forEach(paletteJson::addProperty);
			result.add("palette", paletteJson);
			result.addProperty("seed", seed);
			result.addProperty("center_x", 0);
			result.addProperty("center_z", 0);
			result.addProperty("zoom", 64);
			result.addProperty("grid_sha256", HexFormat.of().formatHex(gridDigest.digest()));
			String expectedNamespace = System.getenv("SQUINCH_PREVIEW_EXPECT_NAMESPACE");
			if (expectedNamespace != null && !expectedNamespace.isBlank()) {
				long expectedPixels = palette.entrySet().stream()
					.filter(entry -> entry.getKey().startsWith(expectedNamespace + ":"))
					.mapToLong(Map.Entry::getValue)
					.sum();
				result.addProperty("expected_namespace", expectedNamespace);
				result.addProperty("expected_namespace_pixels", expectedPixels);
				if (expectedPixels == 0L) {
					throw new IllegalStateException(
						"actual pre-server preview contains no " + expectedNamespace + " biome"
					);
				}
			}
			result.addProperty("preview_source", sourceResult.owned().source().getClass().getName());
			result.addProperty("plain_multi_noise_source", sourceResult.owned().source() instanceof MultiNoiseBiomeSource);
			result.addProperty("capability_nodes", plan.report().nodes().size());
			result.addProperty("composition_state", plan.biomeComposition().descriptor().state().name());
			result.addProperty("decoration_state", plan.selectionDecoration().descriptor().state().name());
			result.addProperty("status", "pass");
		} catch (Throwable failure) {
			result.addProperty("status", "fail");
			result.addProperty("exception", failure.getClass().getName());
			result.addProperty("message", String.valueOf(failure.getMessage()));
		} finally {
			if (sourceResult != null) {
				try {
					sourceResult.owned().close();
				} catch (Exception failure) {
					result.addProperty("cleanup_exception", failure.getClass().getName());
				}
			}
			write(result);
			Minecraft.getInstance().stop();
		}
	}

	private static MessageDigest sha256() {
		try {
			return MessageDigest.getInstance("SHA-256");
		} catch (NoSuchAlgorithmException failure) {
			throw new IllegalStateException("SHA-256 is unavailable", failure);
		}
	}

	private static void write(JsonObject result) {
		String configured = System.getenv("SQUINCH_PRE_SERVER_PREVIEW_RESULT");
		if (configured == null || configured.isBlank()) {
			throw new IllegalStateException("SQUINCH_PRE_SERVER_PREVIEW_RESULT is not configured");
		}
		try {
			Path destination = Path.of(configured).toAbsolutePath();
			Files.createDirectories(destination.getParent());
			Path temporary = destination.resolveSibling(destination.getFileName() + ".tmp");
			Files.writeString(temporary, result + "\n", StandardCharsets.UTF_8);
			Files.move(temporary, destination, StandardCopyOption.REPLACE_EXISTING, StandardCopyOption.ATOMIC_MOVE);
		} catch (Exception failure) {
			throw new IllegalStateException("failed writing pre-server preview result", failure);
		}
	}
}
