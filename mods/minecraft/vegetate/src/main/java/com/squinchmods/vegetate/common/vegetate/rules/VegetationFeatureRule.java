package com.squinchmods.vegetate.common.vegetate.rules;

import java.util.Locale;

public class VegetationFeatureRule {

    public static final boolean ENABLED_DEFAULT = true;

    private boolean enabled = ENABLED_DEFAULT;

    private final String category;

    public VegetationFeatureRule(String category) {
        this.category = category;
    }

    public boolean isUsingDefaultValues() {
        return this.enabled == ENABLED_DEFAULT;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    public String getCategory() {
        return category;
    }

    public boolean isMushroom() {
        return category != null && category.toLowerCase(Locale.ROOT).contains("mushroom");
    }
}
