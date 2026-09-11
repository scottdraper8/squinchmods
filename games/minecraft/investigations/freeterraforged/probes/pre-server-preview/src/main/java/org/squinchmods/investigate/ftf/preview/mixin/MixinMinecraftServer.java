package org.squinchmods.investigate.ftf.preview.mixin;

import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;

import net.minecraft.core.Registry;
import net.minecraft.core.registries.Registries;
import net.minecraft.server.MinecraftServer;
import net.minecraft.world.entity.EntityType;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(MinecraftServer.class)
public abstract class MixinMinecraftServer {
	@Inject(method = "loadLevel", at = @At("HEAD"))
	private void squinch$reportNeoForgeDataMapState(CallbackInfo callback) {
		try {
			MinecraftServer server = (MinecraftServer) (Object) this;
			Registry<EntityType<?>> registry = server.registryAccess().registryOrThrow(Registries.ENTITY_TYPE);
			Class<?> dataMaps = Class.forName("net.neoforged.neoforge.registries.datamaps.builtin.NeoForgeDataMaps");
			Object monsterRoomType = dataMaps.getField("MONSTER_ROOM_MOBS").get(null);
			Method getDataMap = java.util.Arrays.stream(registry.getClass().getMethods())
				.filter(method -> method.getName().equals("getDataMap") && method.getParameterCount() == 1)
				.findFirst()
				.orElseThrow();
			Object entries = getDataMap.invoke(registry, monsterRoomType);
			Class<?> hooks = Class.forName("net.neoforged.neoforge.common.MonsterRoomHooks");
			Field mobsField = hooks.getDeclaredField("monsterRoomMobs");
			mobsField.setAccessible(true);
			Object mobs = mobsField.get(null);
			int entryCount = entries instanceof Map<?, ?> map ? map.size() : -1;
			int hookCount = mobs instanceof java.util.Collection<?> collection ? collection.size() : -1;
			System.err.println("SQUINCH NeoForge data maps at loadLevel: registry=" + entryCount + " hook=" + hookCount);
		} catch (ClassNotFoundException ignored) {
		} catch (ReflectiveOperationException failure) {
			System.err.println("SQUINCH NeoForge data-map inspection failed: " + failure);
			failure.printStackTrace(System.err);
		}
	}
}
