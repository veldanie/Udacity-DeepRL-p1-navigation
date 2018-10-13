import numpy as np
import random

import torch
import torch.nn.functional as F
import torch.optim as optim

from model import QNetwork
from replaybuffer import ReplayBuffer

class DQNAgent():
    """Interacts with and learns from the environment."""

    buffer_size = int(1e5)  # replay buffer size
    batch_size = 64         # minibatch size
    gamma = 0.99            # discount factor
    tau = 1e-3              # for soft update of target parameters
    lr = 5e-4               # learning rate
    update_every = 4        # how often to update the network

    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    def __init__(self, state_size, action_size, seed):
        """Initialize an Agent object.

        Params
        ======
            state_size (int): dimension of each state
            action_size (int): dimension of each action
            seed (int): random seed
        """
        self.state_size = state_size
        self.action_size = action_size
        self.seed = random.seed(seed)

        # Q-Network
        self.qnetwork_local = QNetwork(state_size, action_size, seed).to(self.device)
        self.qnetwork_target = QNetwork(state_size, action_size, seed).to(self.device)
        self.optimizer = optim.Adam(self.qnetwork_local.parameters(), lr=self.lr)

        # Replay memory
        self.memory = ReplayBuffer(action_size, self.buffer_size,
                                   self.batch_size, seed, self.device)
        # Initialize time step (for updating every self.update_every steps)
        self.t_step = 0

    def step(self, state, action, reward, next_state, done):
        # Save experience in replay memory
        self.memory.add(state, action, reward, next_state, done)

        # Learn every self.update_every time steps.
        self.t_step = (self.t_step + 1) % self.update_every
        if self.t_step == 0:
            # If enough samples are available in memory, get random subset and learn
            if len(self.memory) > self.batch_size:
                experiences = self.memory.sample()
                self.learn(experiences, self.gamma)

    def act(self, state, eps=0.):
        """Returns actions for given state as per current policy.

        Params
        ======
            state (array_like): current state
            eps (float): epsilon, for epsilon-greedy action selection
        """
        state = torch.from_numpy(state).float().unsqueeze(0).to(self.device)
        self.qnetwork_local.eval()
        with torch.no_grad():
            action_values = self.qnetwork_local(state)
        self.qnetwork_local.train()

        # Epsilon-greedy action selection
        if random.random() > eps:
            return np.argmax(action_values.cpu().data.numpy())
        else:
            return random.choice(np.arange(self.action_size))

    def learn(self, experiences, gamma):
        """Update value parameters using given batch of experience tuples.

        Params
        ======
            experiences (Tuple[torch.Tensor]): tuple of (s, a, r, s', done) tuples
            gamma (float): discount factor
        """
        states, actions, rewards, next_states, dones = experiences

        # Calculate target value
        self.qnetwork_target.eval()
        with torch.no_grad():
            Q_dash = self.qnetwork_target(next_states)
            Q_dash_max = torch.max(Q_dash, dim=1, keepdim=True)[0]
            y = rewards + gamma * Q_dash_max * (1 - dones)
        self.qnetwork_target.train()

        # Predict Q-value
        self.optimizer.zero_grad()
        Q = self.qnetwork_local(states)
        y_pred = Q.gather(1, actions)

        # TD-error
        loss = torch.sum((y - y_pred)**2)

        # Optimize
        loss.backward()
        self.optimizer.step()

        # ------------------- update target network ------------------- #
        self.soft_update(self.qnetwork_local, self.qnetwork_target, self.tau)

    def soft_update(self, local_model, target_model, tau):
        """Soft update model parameters.
        θ_target = τ*θ_local + (1 - τ)*θ_target

        Params
        ======
            local_model (PyTorch model): weights will be copied from
            target_model (PyTorch model): weights will be copied to
            tau (float): interpolation parameter
        """
        for target_param, local_param in zip(target_model.parameters(), local_model.parameters()):
            target_param.data.copy_(tau*local_param.data + (1.0-tau)*target_param.data)
