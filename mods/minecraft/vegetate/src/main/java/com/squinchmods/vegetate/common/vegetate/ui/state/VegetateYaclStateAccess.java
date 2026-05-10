package com.squinchmods.vegetate.common.vegetate.ui.state;

import dev.isxander.yacl3.api.OptionGroup;
import dev.isxander.yacl3.gui.OptionListWidget;
import dev.isxander.yacl3.gui.SearchFieldWidget;
import dev.isxander.yacl3.gui.YACLScreen;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.HashMap;
import java.util.Map;
import java.util.Optional;
import org.jetbrains.annotations.Nullable;

public final class VegetateYaclStateAccess {
  private VegetateYaclStateAccess() {}

  public static Optional<VegetateScreenState> capture(YACLScreen screen) {
    if (!(screen.tabNavigationBar.getTabManager().getCurrentTab()
        instanceof YACLScreen.CategoryTab categoryTab)) {
      return Optional.empty();
    }

    SearchFieldWidget searchField =
        readTypedField(categoryTab, "searchField", SearchFieldWidget.class);
    OptionListWidget optionList = getOptionListWidget(categoryTab);

    if (searchField == null || optionList == null) {
      return Optional.empty();
    }

    return Optional.of(
        new VegetateScreenState(
            searchField.getValue(),
            getScrollAmount(optionList),
            readGroupExpansionState(optionList)));
  }

  public static void restore(YACLScreen screen, VegetateScreenState state) {
    if (!(screen.tabNavigationBar.getTabManager().getCurrentTab()
        instanceof YACLScreen.CategoryTab categoryTab)) {
      return;
    }

    SearchFieldWidget searchField =
        readTypedField(categoryTab, "searchField", SearchFieldWidget.class);
    OptionListWidget optionList = getOptionListWidget(categoryTab);

    if (searchField == null || optionList == null) {
      return;
    }

    searchField.setValue(state.lastSearchText());
    setScrollAmount(optionList, state.lastScrollAmount());
    applyGroupExpansionState(optionList, state.collapsedGroups());
  }

  private static Map<String, Boolean> readGroupExpansionState(OptionListWidget optionList) {
    Map<String, Boolean> collapsedGroups = new HashMap<>();

    for (OptionListWidget.Entry entry : optionList.children()) {
      if (entry instanceof OptionListWidget.GroupSeparatorEntry groupSeparatorEntry) {
        getGroupName(groupSeparatorEntry)
            .ifPresent(
                groupName ->
                    collapsedGroups.putIfAbsent(groupName, groupSeparatorEntry.isExpanded()));
      }
    }

    return collapsedGroups;
  }

  private static void applyGroupExpansionState(
      OptionListWidget optionList, Map<String, Boolean> collapsedGroups) {
    for (OptionListWidget.Entry entry : optionList.children()) {
      if (entry instanceof OptionListWidget.GroupSeparatorEntry groupSeparatorEntry) {
        getGroupName(groupSeparatorEntry)
            .ifPresent(
                groupName -> {
                  Boolean expanded = collapsedGroups.get(groupName);

                  if (expanded != null) {
                    groupSeparatorEntry.setExpanded(expanded);
                  }
                });
      }
    }
  }

  private static Optional<String> getGroupName(
      OptionListWidget.GroupSeparatorEntry groupSeparatorEntry) {
    OptionGroup group = readTypedField(groupSeparatorEntry, "group", OptionGroup.class);
    return group == null ? Optional.empty() : Optional.of(group.name().getString());
  }

  @Nullable private static OptionListWidget getOptionListWidget(Object tab) {
    Object holder = readField(tab, "optionList");

    if (holder == null) {
      return null;
    }

    for (String methodName : new String[] {"widget", "getWidget", "getType", "getList"}) {
      Object result = invokeNoArg(holder, methodName);

      if (result instanceof OptionListWidget optionListWidget) {
        return optionListWidget;
      }
    }

    return null;
  }

  private static double getScrollAmount(OptionListWidget optionList) {
    Object amount = invokeNoArg(optionList, "scrollAmount");

    if (!(amount instanceof Number)) {
      amount = invokeNoArg(optionList, "getScrollAmount");
    }

    return amount instanceof Number number ? number.doubleValue() : 0.0D;
  }

  private static void setScrollAmount(OptionListWidget optionList, double scrollAmount) {
    Method method = findMethod(optionList.getClass(), "setScrollAmount", double.class);

    if (method == null) {
      return;
    }

    try {
      method.setAccessible(true);
      method.invoke(optionList, scrollAmount);
    } catch (ReflectiveOperationException ignored) {
    }
  }

  @Nullable private static Object invokeNoArg(Object instance, String methodName) {
    Method method = findMethod(instance.getClass(), methodName);

    if (method == null) {
      return null;
    }

    try {
      method.setAccessible(true);
      return method.invoke(instance);
    } catch (ReflectiveOperationException ignored) {
      return null;
    }
  }

  @Nullable private static Method findMethod(Class<?> type, String methodName, Class<?>... parameterTypes) {
    Class<?> current = type;

    while (current != null) {
      try {
        return current.getDeclaredMethod(methodName, parameterTypes);
      } catch (NoSuchMethodException ignored) {
        current = current.getSuperclass();
      }
    }

    return null;
  }

  @Nullable private static <T> T readTypedField(Object instance, String name, Class<T> expectedType) {
    Object value = readField(instance, name);
    return expectedType.isInstance(value) ? expectedType.cast(value) : null;
  }

  @Nullable private static Object readField(Object instance, String name) {
    Class<?> current = instance.getClass();

    while (current != null) {
      try {
        Field field = current.getDeclaredField(name);
        field.setAccessible(true);
        return field.get(instance);
      } catch (NoSuchFieldException ignored) {
        current = current.getSuperclass();
      } catch (ReflectiveOperationException ignored) {
        return null;
      }
    }

    return null;
  }
}
