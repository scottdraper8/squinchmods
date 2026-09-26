import { findGameByHostname } from "#/content/catalog";

export const publicUrlRewrite = {
  input: ({ url }: { url: URL }) => {
    const game = findGameByHostname(url.hostname);

    if (!game) {
      return url;
    }

    const publicPath = url.pathname;
    url.pathname =
      publicPath === "/"
        ? "/games/" + game.slug + "/"
        : "/games/" + game.slug + "/mods" + publicPath;

    return url;
  },
};
