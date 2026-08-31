package org.squinchmods.investigate.rtf;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

import com.google.gson.JsonObject;

import net.minecraft.server.MinecraftServer;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.level.chunk.ChunkGenerator;
import org.squinchmods.investigate.ProbeExecution;
import org.squinchmods.investigate.ProbePack;
import org.squinchmods.investigate.ProbePhase;
import org.squinchmods.investigate.ProbeRegistry;
import org.squinchmods.investigate.ProbeRequest;
import org.squinchmods.investigate.ProbeResult;
import org.squinchmods.investigate.TerminalState;
import raccoonman.reterraforged.world.worldgen.RTFRandomState;
import raccoonman.reterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenEpoch;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenOwnerType;
import raccoonman.reterraforged.world.worldgen.runtime.WorldgenPlan;

/** Verifies an owner-preserving, atomic typed-plan rebind across a real tag reload. */
public final class WorldgenLifecycleProbePack implements ProbePack {
    private static final Map<String, Snapshot> BASELINES = new ConcurrentHashMap<>();

    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-worldgen-lifecycle", "1", LifecycleProbe::new);
    }

    private static final class LifecycleProbe implements ProbeExecution {
        private final String runId;
        private final int maxWaitTicks;
        private int waitedTicks;

        private LifecycleProbe(ProbeRequest request) {
            this.runId = request.runId();
            this.maxWaitTicks = request.config().has("max_wait_ticks")
                ? request.config().get("max_wait_ticks").getAsInt()
                : 600;
            if (this.maxWaitTicks < 1) {
                throw new IllegalArgumentException("max_wait_ticks must be positive");
            }
        }

        @Override
        public ProbeResult tick(MinecraftServer server) {
            ServerLevel level = server.overworld();
            ChunkGenerator root = level.getChunkSource().getGenerator();
            if (!(root instanceof TerraForgedChunkGenerator generator)) {
                return failure("active generator is not the registered FTF root: " + root.getClass().getName());
            }

            WorldgenEpoch epoch = generator.epoch().orElse(null);
            WorldgenPlan plan = generator.plan().orElse(null);
            RTFRandomState randomState = (RTFRandomState) (Object) level.getChunkSource().randomState();
            if (epoch == null || plan == null || randomState.epoch() == null || randomState.plan() == null) {
                return failure("FTF root, RandomState, epoch, and plan were not fully bound");
            }

            Snapshot current = new Snapshot(epoch, plan, randomState.epoch(), randomState.plan());
            Snapshot baseline = BASELINES.putIfAbsent(this.runId, current);
            if (baseline == null) {
                JsonObject data = snapshot("baseline", current);
                data.addProperty("baseline_captured", true);
                return ProbeResult.complete(TerminalState.PASS, ProbePhase.RELOAD, data, 4);
            }

            if (current.epoch().tagEpoch().sequence() <= baseline.epoch().tagEpoch().sequence()) {
                if (++this.waitedTicks < this.maxWaitTicks) {
                    return null;
                }
                BASELINES.remove(this.runId, baseline);
                JsonObject data = snapshot("unchanged", current);
                data.addProperty("error", "tag epoch did not advance before the probe timeout");
                data.addProperty("baseline_tag_sequence", baseline.epoch().tagEpoch().sequence());
                return ProbeResult.complete(TerminalState.FAIL, ProbePhase.RELOAD, data, 4);
            }

            boolean sameEpoch = current.epoch().id().equals(baseline.epoch().id());
            boolean advancedOnce = current.epoch().tagEpoch().sequence()
                == baseline.epoch().tagEpoch().sequence() + 1L;
            boolean fingerprintChanged = !current.epoch().tagEpoch().fingerprint()
                .equals(baseline.epoch().tagEpoch().fingerprint());
            boolean planReplaced = current.plan() != baseline.plan();
            boolean generatorOwnerAligned = current.plan().owner().id().equals(current.epoch().id())
                && current.plan().owner().type() == WorldgenOwnerType.WORLDGEN_EPOCH;
            boolean randomStateOwnerAligned = current.randomStateEpoch() == current.epoch()
                && current.randomStatePlan() == current.plan();
            boolean immutableBootstrapInputs = current.epoch().settingsIdentity()
                .equals(baseline.epoch().settingsIdentity())
                && current.epoch().resourceLayerFingerprint()
                    .equals(baseline.epoch().resourceLayerFingerprint());
            boolean reportsPresent = !baseline.plan().report().nodes().isEmpty()
                && !current.plan().report().nodes().isEmpty();
            boolean passed = sameEpoch && advancedOnce && fingerprintChanged && planReplaced
                && generatorOwnerAligned && randomStateOwnerAligned && immutableBootstrapInputs
                && reportsPresent;

            JsonObject data = new JsonObject();
            data.add("before", snapshot("before", baseline));
            data.add("after", snapshot("after", current));
            data.addProperty("same_worldgen_epoch_id", sameEpoch);
            data.addProperty("tag_epoch_advanced_once", advancedOnce);
            data.addProperty("tag_fingerprint_changed", fingerprintChanged);
            data.addProperty("plan_replaced", planReplaced);
            data.addProperty("generator_owner_aligned", generatorOwnerAligned);
            data.addProperty("random_state_owner_aligned", randomStateOwnerAligned);
            data.addProperty("bootstrap_inputs_preserved", immutableBootstrapInputs);
            data.addProperty("capability_reports_present", reportsPresent);
            BASELINES.remove(this.runId, baseline);
            return ProbeResult.complete(
                passed ? TerminalState.PASS : TerminalState.FAIL,
                ProbePhase.RELOAD,
                data,
                8
            );
        }

        private static ProbeResult failure(String error) {
            JsonObject data = new JsonObject();
            data.addProperty("error", error);
            return ProbeResult.complete(TerminalState.FAIL, ProbePhase.RELOAD, data, 0);
        }
    }

    private static JsonObject snapshot(String phase, Snapshot snapshot) {
        JsonObject data = new JsonObject();
        data.addProperty("snapshot", phase);
        data.addProperty("epoch_id", snapshot.epoch().id().toString());
        data.addProperty("owner_type", snapshot.plan().owner().type().name().toLowerCase());
        data.addProperty("tag_sequence", snapshot.epoch().tagEpoch().sequence());
        data.addProperty("tag_fingerprint", snapshot.epoch().tagEpoch().fingerprint());
        data.addProperty("plan_identity", System.identityHashCode(snapshot.plan()));
        data.addProperty("report_nodes", snapshot.plan().report().nodes().size());
        data.addProperty("feature_pipelines", snapshot.plan().placedFeatures().pipelines().size());
        data.addProperty("carver_pipelines", snapshot.plan().carvers().pipelines().size());
        data.addProperty("structures", snapshot.plan().structures().structures().size());
        data.addProperty("random_state_epoch_same_instance", snapshot.randomStateEpoch() == snapshot.epoch());
        data.addProperty("random_state_plan_same_instance", snapshot.randomStatePlan() == snapshot.plan());
        return data;
    }

    private record Snapshot(
        WorldgenEpoch epoch,
        WorldgenPlan plan,
        WorldgenEpoch randomStateEpoch,
        WorldgenPlan randomStatePlan
    ) {
    }
}
