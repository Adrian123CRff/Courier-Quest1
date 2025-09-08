class Inventory:
    def __init__(self):
        self.items = []
        self.max_weight = 10

    def add_item(self, item):
        if self.get_total_weight() + item["weight"] <= self.max_weight:
            self.items.append(item)
            return True
        return False

    def get_total_weight(self):
        return sum(item["weight"] for item in self.items)
