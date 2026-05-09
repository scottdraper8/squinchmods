package com.squinchmods.treeify.common;

import com.squinchmods.treeify.common.treeify.rules.TreeifyConfigService;
import net.minecraft.resources.Identifier;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

public final class Treeify
{
	public static final String MOD_ID = "treeify";
	private static final Logger LOGGER = LoggerFactory.getLogger(Treeify.MOD_ID);
	private static final TreeifyConfigService CONFIG_SERVICE = new TreeifyConfigService();

	public static TreeifyConfigService getConfigService() {
		return CONFIG_SERVICE;
	}

	public static Logger getLogger() {
		return LOGGER;
	}

	public static Identifier makeId(String path) {
		//? if >=1.21 {
		return Identifier.tryBuild(MOD_ID, path);
		//?} else {
		/*return new Identifier(MOD_ID, path);
		*///?}
	}

	public static void init() {
		CONFIG_SERVICE.create();
		CONFIG_SERVICE.load();
	}
}
