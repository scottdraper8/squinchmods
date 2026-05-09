package com.squinchmods.treeify.common.api;

import net.minecraft.network.chat.Component;

/**
 * Interface injected into YACL options via mixins to provide custom behavior.
 */
public interface TreeifyOption {
    void treeify$setName(Component name);
}
