package org.squinchmods.investigate;

@FunctionalInterface
public interface ProbeFactory {
    ProbeExecution create(ProbeRequest request) throws Exception;
}
