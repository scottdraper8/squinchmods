package org.squinchmods.investigate;

public enum TerminalState {
    PASS("pass"),
    FAIL("fail"),
    INCONCLUSIVE("inconclusive"),
    ERROR("error");

    private final String wireName;

    TerminalState(String wireName) {
        this.wireName = wireName;
    }

    public String wireName() {
        return this.wireName;
    }
}
