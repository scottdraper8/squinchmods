package org.squinchmods.investigate;

public enum ProbePhase {
    PREDICTION("prediction"),
    STRUCTURE_START("structure-start"),
    GENERATION("generation"),
    PLACEMENT("placement"),
    FINISHED_CHUNK("finished-chunk"),
    RELOAD("reload");

    private final String wireName;

    ProbePhase(String wireName) {
        this.wireName = wireName;
    }

    public String wireName() {
        return this.wireName;
    }
}
