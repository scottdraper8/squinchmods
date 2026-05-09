package com.squinchmods.treeify.common.treeify.rules;

import java.util.Locale;

public class VegetationFeatureRule {

    public static final boolean ENABLED_DEFAULT = true;
    public static final float DENSITY_MULTIPLIER_DEFAULT = 1.0f;
    public static final int HEIGHT_DELTA_DEFAULT = 0;

    private boolean enabled = ENABLED_DEFAULT;
    private float densityMultiplier = DENSITY_MULTIPLIER_DEFAULT;
    private int heightDelta = HEIGHT_DELTA_DEFAULT;

    // Metadata from Phase 2 (Honest Schema)
    private final String category;
    private final boolean supportsDensity;
    private final boolean supportsHeight;

    public VegetationFeatureRule(String category, boolean supportsDensity, boolean supportsHeight) {
        this.category = category;
        this.supportsDensity = supportsDensity;
        this.supportsHeight = supportsHeight;
    }

    public boolean isUsingDefaultValues() {
        return this.enabled == ENABLED_DEFAULT &&
               Float.compare(this.densityMultiplier, DENSITY_MULTIPLIER_DEFAULT) == 0 &&
               this.heightDelta == HEIGHT_DELTA_DEFAULT;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public float getDensityMultiplier() {
        return supportsDensity ? densityMultiplier : DENSITY_MULTIPLIER_DEFAULT;
    }

    public void setDensityMultiplier(float densityMultiplier) {
        if (supportsDensity) {
            this.densityMultiplier = densityMultiplier;
        }
    }

    public int getHeightDelta() {
        return supportsHeight ? heightDelta : HEIGHT_DELTA_DEFAULT;
    }

    public void setHeightDelta(int heightDelta) {
        if (supportsHeight) {
            this.heightDelta = heightDelta;
        }
    }

    public String getCategory() {
        return category;
    }

    public boolean isTree() {
        if (category == null) {
            return false;
        }

        String normalizedCategory = category.toLowerCase(Locale.ROOT);
        return normalizedCategory.contains("tree") || normalizedCategory.equals("mixed_vegetation");
    }

    public boolean isMushroom() {
        return category != null && category.toLowerCase(Locale.ROOT).contains("mushroom");
    }

    public boolean supportsDensity() {
        return supportsDensity;
    }

    public boolean supportsHeight() {
        return supportsHeight;
    }
}
