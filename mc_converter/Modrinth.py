from .Helpers.abstractions import ModpackManager

class ModrinthManager(ModpackManager):

    def get_resource(self, resource: dict[str]):
        return super().get_resource(resource)

    def get_override(self, file: dict[str]):
        return super().get_override(file)

    def parse(self) -> None:
        return super().parse()

    def add_resource(self, resource: dict[str]):
        return super().add_resource(resource)

    def add_override(self, file: dict[str]):
        return super().add_override(file)

    def write(self) -> None:
        return super().write()
