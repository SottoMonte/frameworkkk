import torch
import torch.nn as nn
import os

import framework.port.network as network

class Adapter(network.Port, nn.Module):
    def __init__(self, **kwargs):
        #super().__init__()
        nn.Module.__init__(self)   # ✔️ inizializza PyTorch
        network.Port.__init__(self) 
        tipo = kwargs.get('tipo', 'linear')
        input = kwargs.get('input', 32)
        output = kwargs.get('output', 32)
        self.layers = nn.ModuleList()
        match tipo:
            case 'spiking':
                self.layers.append(nn.Parameter(input, requires_grad=False))
                self.layers.append(nn.Parameter(output, requires_grad=False))
            case 'linear':
                self.layers.append(nn.Linear(input, output))
                self.forward = self._forward_linear
            case _:
                raise ValueError(f"Tipo di rete non supportato: {tipo}")

    def compute(self, *args):
        # Implementazione della logica di calcolo della rete neurale
        # Questo è un esempio generico; dovresti adattarlo alle tue esigenze specifiche.
        input_sequence = args[0]  # Supponendo che il primo argomento sia la sequenza di input
        return self.forward(input_sequence)

    def forward2(self, input_sequence):
        batch_size, time_steps, _ = input_sequence.shape
        membrane_potential = torch.zeros(batch_size, self.reservoir_size, device=input_sequence.device)
        spikes = torch.zeros_like(membrane_potential)
        spike_history = []

        for t in range(time_steps):
            x_t = input_sequence[:, t, :]
            current_input = torch.matmul(x_t, self.w_in.t()) + torch.matmul(spikes, self.w_rec.t())
            membrane_potential = (membrane_potential * self.leak_rate) + current_input
            spikes = (membrane_potential >= self.threshold).float()
            membrane_potential = membrane_potential * (1.0 - spikes)
            spike_history.append(spikes)

        return torch.stack(spike_history, dim=1), None

    def _forward_linear(self, x):
        x_flat = x.flatten(start_dim=1)
        return self.layers[-1](x_flat)