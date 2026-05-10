package com.squinchmods.vegetate.common.mixin.plugin;

import java.util.List;
import java.util.Set;
import org.jetbrains.annotations.Nullable;
import org.objectweb.asm.tree.ClassNode;
import org.spongepowered.asm.mixin.extensibility.IMixinConfigPlugin;
import org.spongepowered.asm.mixin.extensibility.IMixinInfo;

public class VegetateMixinPlugin implements IMixinConfigPlugin {
  @Override
  public void onLoad(String mixinPackage) {}

  @Override
  public @Nullable String getRefMapperConfig() {
    return null;
  }

  @Override
  public boolean shouldApplyMixin(String targetClassName, String mixinClassName) {
    if (mixinClassName.equals("com.squinchmods.vegetate.common.mixin.WorldOpenFlowsMixin")) {
      return this.isClassAvailable("me.earth.mc_runtime_test.McRuntimeTest");
    }

    return true;
  }

  @Override
  public void acceptTargets(Set<String> myTargets, Set<String> otherTargets) {}

  @Override
  public @Nullable List<String> getMixins() {
    return null;
  }

  @Override
  public void preApply(
      String targetClassName, ClassNode targetClass, String mixinClassName, IMixinInfo mixinInfo) {}

  @Override
  public void postApply(
      String targetClassName, ClassNode targetClass, String mixinClassName, IMixinInfo mixinInfo) {}

  private boolean isClassAvailable(String className) {
    String classPath = className.replace('.', '/') + ".class";
    return getClass().getClassLoader().getResource(classPath) != null;
  }
}
