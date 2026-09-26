package org.squinchmods.investigate.ftf.stagewrapper;

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
import etcodehome.freeterraforged.world.worldgen.runtime.TerraForgedChunkGenerator;

public final class GeneratorStageWrapperProbePack implements ProbePack {
    @Override
    public void register() {
        ProbeRegistry.register("squinch:ftf-generator-stage-wrapper", "1", WrapperProbe::new);
    }

    private static final class WrapperProbe implements ProbeExecution {
        private WrapperProbe(ProbeRequest request) {
        }

        @Override
        public ProbeResult tick(MinecraftServer server) {
            ServerLevel level = server.overworld();
            ChunkGenerator root = level.getChunkSource().getGenerator();
            JsonObject data = new JsonObject();
            data.addProperty("active_generator", root.getClass().getName());
            if (!(root instanceof TerraForgedChunkGenerator generator)) {
                data.addProperty("error", "active generator is not the FTF runtime root");
                return ProbeResult.complete(TerminalState.FAIL, ProbePhase.FINISHED_CHUNK, data, 0);
            }
            long calls = GeneratorStageWrapperTelemetry.ftfSurfaceWrapperCalls();
            data.addProperty("ftf_surface_wrapper_calls", calls);
            generator.plan().ifPresent(plan -> data.add("plan_diagnostics", plan.diagnostics().toJson()));
            if (calls == 0L) {
                data.addProperty("error", "vanilla NoiseBasedChunkGenerator.buildSurface wrapper never observed FTF");
            }
            return ProbeResult.complete(
                calls > 0L ? TerminalState.PASS : TerminalState.FAIL,
                ProbePhase.FINISHED_CHUNK,
                data,
                calls > 0L ? 1 : 0
            );
        }
    }
}
