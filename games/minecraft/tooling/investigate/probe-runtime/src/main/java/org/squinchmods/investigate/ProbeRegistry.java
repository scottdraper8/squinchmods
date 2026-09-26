package org.squinchmods.investigate;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

public final class ProbeRegistry {
    private static final Map<String, RegisteredProbe> PROBES = new ConcurrentHashMap<>();

    private ProbeRegistry() {
    }

    public static void register(String id, String version, ProbeFactory factory) {
        RegisteredProbe previous = PROBES.putIfAbsent(id, new RegisteredProbe(version, factory));
        if (previous != null) {
            throw new IllegalStateException("duplicate probe ID: " + id);
        }
    }

    static RegisteredProbe find(String id) {
        return PROBES.get(id);
    }

    record RegisteredProbe(String version, ProbeFactory factory) {
    }
}
