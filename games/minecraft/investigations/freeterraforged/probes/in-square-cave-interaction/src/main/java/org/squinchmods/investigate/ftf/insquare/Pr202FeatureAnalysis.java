package org.squinchmods.investigate.ftf.insquare;

import java.lang.reflect.Field;
import java.lang.reflect.Modifier;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.IdentityHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Optional;
import java.util.Set;

import net.minecraft.core.Holder;
import net.minecraft.core.Vec3i;
import net.minecraft.util.valueproviders.IntProvider;
import net.minecraft.world.level.levelgen.feature.ConfiguredFeature;
import net.minecraft.world.level.levelgen.placement.PlacedFeature;
import net.minecraft.world.level.levelgen.placement.PlacementModifier;

/** Mirrors the current PR #202 object-graph classifier while retaining the first unsafe path. */
final class Pr202FeatureAnalysis {
    private Pr202FeatureAnalysis() {
    }

    static Result inspect(PlacedFeature placedFeature) {
        return inspect(placedFeature, false);
    }

    /** The per-placed-feature decision without PR #202's merged static cache fields. */
    static Result inspectIntrinsic(PlacedFeature placedFeature) {
        return inspect(placedFeature, true);
    }

    private static Result inspect(PlacedFeature placedFeature, boolean skipStaticFields) {
        Set<Object> visited = Collections.newSetFromMap(new IdentityHashMap<>());
        List<PlacementModifier> modifiers = placedFeature.placement();
        for (int index = 0; index < modifiers.size(); index++) {
            Optional<String> reason = inspectObjectGraph(
                modifiers.get(index),
                visited,
                0,
                "placement[" + index + "]",
                skipStaticFields
            );
            if (reason.isPresent()) {
                return new Result(true, reason.get());
            }
        }

        Holder<ConfiguredFeature<?, ?>> holder = placedFeature.feature();
        if (holder.isBound()) {
            Optional<String> reason = inspectObjectGraph(
                holder.value().config(),
                visited,
                0,
                "configured_feature.config",
                skipStaticFields
            );
            if (reason.isPresent()) {
                return new Result(true, reason.get());
            }
        }
        return new Result(false, "");
    }

    private static Optional<String> inspectObjectGraph(
        Object object,
        Set<Object> visited,
        int depth,
        String path,
        boolean skipStaticFields
    ) {
        if (object == null || depth > 5 || !visited.add(object)) {
            return Optional.empty();
        }

        if (depth > 0 && (object instanceof PlacedFeature || object instanceof ConfiguredFeature)) {
            return Optional.empty();
        }

        if (object instanceof Vec3i vec && (vec.getX() != 0 || vec.getZ() != 0)) {
            return Optional.of(path + "=<" + vec.getX() + "," + vec.getY() + "," + vec.getZ() + ">");
        }

        Class<?> type = object.getClass();
        String packageName = type.getPackageName();
        if (packageName.startsWith("java.lang") || packageName.startsWith("java.math") || type.isEnum()) {
            return Optional.empty();
        }

        if (object instanceof Iterable<?> iterable) {
            int index = 0;
            for (Object item : iterable) {
                Optional<String> reason = inspectObjectGraph(
                    item, visited, depth + 1, path + "[" + index++ + "]", skipStaticFields
                );
                if (reason.isPresent()) {
                    return reason;
                }
            }
            return Optional.empty();
        }
        if (object instanceof Optional<?> optional) {
            return optional.isPresent()
                ? inspectObjectGraph(optional.get(), visited, depth + 1, path + ".value", skipStaticFields)
                : Optional.empty();
        }
        if (object instanceof Holder<?> holder) {
            if (!holder.isBound()) {
                return Optional.empty();
            }
            Object value = holder.value();
            if (value instanceof PlacedFeature || value instanceof ConfiguredFeature) {
                return Optional.empty();
            }
            return inspectObjectGraph(value, visited, depth + 1, path + ".value", skipStaticFields);
        }
        if (type.isArray()) {
            int length = java.lang.reflect.Array.getLength(object);
            for (int index = 0; index < length; index++) {
                Optional<String> reason = inspectObjectGraph(
                    java.lang.reflect.Array.get(object, index),
                    visited,
                    depth + 1,
                    path + "[" + index + "]",
                    skipStaticFields
                );
                if (reason.isPresent()) {
                    return reason;
                }
            }
            return Optional.empty();
        }

        for (Field field : getDeclaredFields(type)) {
            if (skipStaticFields && Modifier.isStatic(field.getModifiers())) {
                continue;
            }
            try {
                field.setAccessible(true);
                Object value = field.get(object);
                if (value == null) {
                    continue;
                }
                String fieldPath = path + "." + field.getName();
                String name = field.getName().toLowerCase(Locale.ROOT);
                if ((name.contains("xz") || name.contains("offset") || name.contains("spread"))
                    && value instanceof IntProvider provider
                    && (provider.getMinValue() != 0 || provider.getMaxValue() != 0)) {
                    return Optional.of(
                        fieldPath + "=[" + provider.getMinValue() + "," + provider.getMaxValue() + "]"
                    );
                }
                Optional<String> reason = inspectObjectGraph(
                    value, visited, depth + 1, fieldPath, skipStaticFields
                );
                if (reason.isPresent()) {
                    return reason;
                }
            } catch (Exception ignored) {
                // PR #202 also treats inaccessible fields as non-evidence.
            }
        }
        return Optional.empty();
    }

    private static List<Field> getDeclaredFields(Class<?> type) {
        List<Field> fields = new ArrayList<>();
        Class<?> current = type;
        while (current != null
            && current != Object.class
            && !current.getPackageName().startsWith("java.lang")) {
            fields.addAll(Arrays.asList(current.getDeclaredFields()));
            current = current.getSuperclass();
        }
        return fields;
    }

    record Result(boolean unsafe, String reason) {
    }
}
