package com.squinchmods.treeify.common.treeify.worldgen.clone;

import net.minecraft.resources.Identifier;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Tracks the origin of cloned features for traceability.
 */
public final class ProvenanceTracker {

    private static final Map<Object, Identifier> PROVENANCE = new ConcurrentHashMap<>();

    /**
     * Records that a clone was created from an original feature.
     *
     * @param clone      The cloned object (PlacedFeature or ConfiguredFeature).
     * @param originalId The ID of the original feature.
     */
    public static void record(Object clone, Identifier originalId) {
        if (clone != null && originalId != null) {
            PROVENANCE.put(clone, originalId);
        }
    }

    /**
     * Gets the original ID of a cloned feature.
     *
     * @param clone The cloned object.
     * @return The original ID, or null if not a tracked clone.
     */
    public static Identifier getOriginalId(Object clone) {
        return PROVENANCE.get(clone);
    }

    private ProvenanceTracker() {
    }
}
