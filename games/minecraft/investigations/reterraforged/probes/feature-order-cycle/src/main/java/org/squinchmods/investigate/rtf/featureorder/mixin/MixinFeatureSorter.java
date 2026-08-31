package org.squinchmods.investigate.rtf.featureorder.mixin;

import java.util.IdentityHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Function;

import com.mojang.logging.LogUtils;
import net.minecraft.core.Holder;
import net.minecraft.core.HolderSet;
import net.minecraft.world.level.biome.FeatureSorter;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import org.slf4j.Logger;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

/** Reports identity duplicates that make one source's flattened feature order cyclic. */
@Mixin(FeatureSorter.class)
abstract class MixinFeatureSorter {
    private static final Logger LOGGER = LogUtils.getLogger();
    private static final Set<String> REPORTED = ConcurrentHashMap.newKeySet();

    @Inject(method = "buildFeaturesPerStep", at = @At("HEAD"))
    private static <T> void squinch$reportDuplicateFeatureIdentities(
        List<T> sources,
        Function<T, List<HolderSet<PlacedFeature>>> featuresByStep,
        boolean reportInvolvedSources,
        CallbackInfoReturnable<List<FeatureSorter.StepFeatureData>> callback
    ) {
        for (T source : sources) {
            Map<PlacedFeature, Seen> seen = new IdentityHashMap<>();
            List<HolderSet<PlacedFeature>> steps = featuresByStep.apply(source);
            for (int step = 0; step < steps.size(); step++) {
                int index = 0;
                for (Holder<PlacedFeature> holder : steps.get(step)) {
                    String id = holder.unwrapKey()
                        .map(key -> key.location().toString())
                        .orElse("<direct>");
                    Seen previous = seen.putIfAbsent(holder.value(), new Seen(step, index, id));
                    if (previous != null && REPORTED.add(
                        source + "\u0000" + id
                            + "\u0000" + previous.step()
                            + "\u0000" + previous.index()
                            + "\u0000" + previous.id()
                            + "\u0000" + step
                            + "\u0000" + index
                    )) {
                        LOGGER.error(
                            "SQUINCH_FEATURE_ORDER_DUPLICATE source={} feature={} "
                                + "first_step={} first_index={} second_step={} second_index={} "
                                + "first_holder={}",
                            source,
                            id,
                            previous.step(),
                            previous.index(),
                            step,
                            index,
                            previous.id()
                        );
                    }
                    index++;
                }
            }
        }
    }

    private record Seen(int step, int index, String id) {
    }
}
