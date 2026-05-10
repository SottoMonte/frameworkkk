class Network:

    def __init__(self):
        self.nodes = {}
        self.edges = {}
        self.layers = []

    # -------------------------
    # NODI
    # -------------------------

    def add_node(self, node_id, data=None):
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "data": data
            }
            self.edges[node_id] = []

    def remove_node(self, node_id):

        if node_id not in self.nodes:
            return

        del self.nodes[node_id]
        del self.edges[node_id]

        # rimuove connessioni entranti
        for src in self.edges:
            self.edges[src] = [
                e for e in self.edges[src]
                if e["to"] != node_id
            ]

    # -------------------------
    # CONNESSIONI
    # -------------------------

    def connect(self, src, dst, weight=1.0):

        if src not in self.nodes:
            return

        if dst not in self.nodes:
            return

        self.edges[src].append({
            "to": dst,
            "weight": weight
        })

    def disconnect(self, src, dst):

        if src not in self.edges:
            return

        self.edges[src] = [
            e for e in self.edges[src]
            if e["to"] != dst
        ]

    # -------------------------
    # LAYERS
    # -------------------------

    def add_layer(self, nodes):

        self.layers.append(nodes)

    # -------------------------
    # INFO
    # -------------------------

    def get_neighbors(self, node_id):

        if node_id not in self.edges:
            return []

        return self.edges[node_id]

    def get_node(self, node_id):

        return self.nodes.get(node_id)

    def show(self):

        print("NODES:")
        for node_id in self.nodes:
            print(node_id, self.nodes[node_id])

        print("\nEDGES:")
        for src in self.edges:
            for edge in self.edges[src]:
                print(
                    f"{src} -> {edge['to']} "
                    f"(w={edge['weight']})"
                )

        print("\nLAYERS:")
        for i, layer in enumerate(self.layers):
            print(f"Layer {i}: {layer}")