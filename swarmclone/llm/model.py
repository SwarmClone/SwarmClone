# Nvidia的新模型：nGPT
# 是的没错这就是MiniLM
import torch
from torch import nn
import torch.nn.functional as F

normalize = lambda x, dim=-1: F.normalize(x, p=2, dim=dim)

class RotatoryPositionalEncoding(nn.Module):
    """旋转位置编码"""
    def __init__(self, dim: int, max_length: int):
        super().__init__()
        assert dim % 2 == 0
        positions = torch.arange(0, max_length, 1)
        theta = 1 / 10000 ** (torch.arange(0, dim, 2) / dim) # thetai = 1/10000^(2i/dim)
        """
            theta0  theta1  theta2  theta3 ... theta(dim/2-1)
        m=0 0theta0 0theta1 0theta2 0theta3
        m=1 1theta0 1theta1 1theta2 1theta3
        m=2 2theta0 2theta1 2theta2 2theta3
        m=3 3theta0 3theta1 3theta2 3theta3
        ...
        m=max_length-1                         ...
        """
        positions_theta = positions.unsqueeze(1) * theta.unsqueeze(0) # (max_length, dim//2)
        positions_sin = torch.sin(positions_theta)
        positions_cos = torch.cos(positions_theta)
        self.register_buffer('positions_sin', positions_sin)
        self.register_buffer('positions_cos', positions_cos)
        self.dim = dim

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_real = x[..., :self.dim // 2] # (x.size(-2), dim//2)
        x_imag = x[...,  self.dim // 2:]
        pos_cos = self.positions_cos[:x.size(-2)] # (x.size(-2), dim//2)
        pos_sin = self.positions_sin[:x.size(-2)]
        y_real = x_real * pos_cos - x_imag * pos_sin
        y_imag = x_real * pos_sin + x_imag * pos_cos
        return torch.cat([y_real, y_imag], dim=-1)
        
class MLP(nn.Module):
    def __init__(self, dim: int, hidden_dim: int, dropout: float):
        super().__init__()
        self.dim = dim
        self.u_proj = nn.Linear(dim, hidden_dim, bias=False)
        self.v_proj = nn.Linear(dim, hidden_dim, bias=False)
        self.o_proj = nn.Linear(hidden_dim, dim, bias=False)
        self.dropout = nn.Dropout(dropout)

        # uv的缩放因子
        suinit = 1.0
        suscale = 1.0
        self.restore_scale_su = suinit / suscale
        self.su = nn.Parameter(torch.ones(hidden_dim) * suscale)
        svinit = 1.0
        svscale = 1.0
        self.restore_scale_sv = svinit / svscale
        self.sv = nn.Parameter(torch.ones(hidden_dim) * svscale)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        actual_su = self.su * self.restore_scale_su
        actual_sv = self.sv * self.restore_scale_sv
        u = self.u_proj(x) * actual_su
        v = self.v_proj(x) * actual_sv * self.dim ** 0.5
        return normalize(self.o_proj(self.dropout(u * nn.functional.silu(v))))

    @torch.no_grad()
    def normalize(self) -> None:
        self.u_proj.weight.data.copy_(normalize(self.u_proj.weight.data))
        self.v_proj.weight.data.copy_(normalize(self.v_proj.weight.data))
        self.o_proj.weight.data.copy_(normalize(self.o_proj.weight.data, 0))

class CausalSelfAttention(nn.Module):
    """带因果关系的多头自注意力，使用Flash Attention和RoPE"""
    def __init__(self, dim: int, max_length: int, n_heads: int, dropout: float):
        super().__init__()
        assert dim % n_heads == 0
        self.n_heads = n_heads
        self.head_dim = dim // n_heads
        self.q_proj = nn.Linear(dim, dim, bias=False)
        self.k_proj = nn.Linear(dim, dim, bias=False)
        self.v_proj = nn.Linear(dim, dim, bias=False)
        self.o_proj = nn.Linear(dim, dim, bias=False)
        self.pe = RotatoryPositionalEncoding(self.head_dim, max_length)
        self.dropout = dropout

        # QK的缩放因子
        sqkinit = 1.0
        sqkscale = 1 / dim ** 0.5
        self.restore_scale_sqk = sqkinit / sqkscale
        self.sqk = nn.Parameter(torch.ones(n_heads, 1, self.head_dim) * sqkscale)

    def forward(self, x: torch.Tensor):
        B, T, C = x.shape
        actual_sqk = self.sqk * self.restore_scale_sqk # (n_heads, 1, head_dim)
        # (B, T, C) -proj-> (B, T, C)
        # -view-> (B, T, n_heads, head_dim)
        # -T(1, 2)-> (B, n_heads, T, head_dim)
        q = self.pe(self.q_proj(x).view(B, T, self.n_heads, -1).transpose(1, 2)) * actual_sqk
        k = self.pe(self.k_proj(x).view(B, T, self.n_heads, -1).transpose(1, 2)) * actual_sqk
        v = self.v_proj(x).view(B, T, self.n_heads, -1).transpose(1, 2)
        # (B, n_heads, T, head_dim) -T(1, 2)-> (B, T, n_heads, head_dim)
        # -view-> (B, T, C)
        x = (
            nn.functional.scaled_dot_product_attention(q, k, v,
                    is_causal=True, dropout_p=self.dropout,
                    scale=self.head_dim ** 0.5)
            .transpose(1, 2)
            .reshape(B, T, C)
        )
        return normalize(self.o_proj(x))

    @torch.no_grad()
    def normalize(self) -> None:
        self.q_proj.weight.data.copy_(normalize(self.q_proj.weight.data))
        self.k_proj.weight.data.copy_(normalize(self.k_proj.weight.data))
        self.v_proj.weight.data.copy_(normalize(self.v_proj.weight.data))
        self.o_proj.weight.data.copy_(normalize(self.o_proj.weight.data, 0))

class Block(nn.Module):
    """一个Decoder块"""
    def __init__(self, dim: int, max_length: int, n_heads: int, dropout: float):
        super().__init__()
        self.attn = CausalSelfAttention(dim, max_length, n_heads, dropout)
        self.mlp = MLP(dim, dim * 4, dropout)

        # 自带的学习率
        lrinit_a = 0.05
        lrscale_a = 1 / dim ** 0.5
        self.restore_scale_a = lrinit_a / lrscale_a
        self.lr_a = nn.Parameter(torch.ones(dim) * lrscale_a)
        lrinit_m = 0.05
        lrscale_m = 1 / dim ** 0.5
        self.restore_scale_m = lrinit_m / lrscale_m
        self.lr_m = nn.Parameter(torch.ones(dim) * lrscale_m)

    def forward(self, x: torch.Tensor):
        actual_lr_a = self.lr_a * self.restore_scale_a
        actual_lr_m = self.lr_m * self.restore_scale_m
        x = normalize(x + (self.attn(x) - x) * actual_lr_a)
        x = normalize(x + (self.mlp(x) - x) * actual_lr_m)
        return x

    @torch.no_grad()
    def normalize(self) -> None:
        self.attn.normalize()
        self.mlp.normalize()

class LLM(nn.Module):
    """大模型本体"""
    def __init__(self, vocab_size: int, dim: int, max_length: int, n_heads: int,
                n_blocks: int, dropout: float):
        super().__init__()
        self.wte = nn.Embedding(vocab_size, dim)
        self.blocks = nn.ModuleList([
            Block(dim, max_length, n_heads, dropout) for _ in range(n_blocks)
        ])
        self.lmhead = nn.Linear(dim, vocab_size)

        # Logit缩放因数
        szinit = 1.0
        szscale = 1 / dim ** 0.5
        self.restore_scale = szinit / szscale
        self.sz = nn.Parameter(torch.ones(vocab_size) * szscale)

        self.normalize()

    def forward(self, x: torch.Tensor):
        x = self.wte(x)
        for block in self.blocks:
            x = block(x)
        x = self.lmhead(x)
        actual_sz = self.sz * self.restore_scale
        return x * actual_sz

    def save(self, path: str):
        torch.save(self.state_dict(), path) # 保存模型参数防止带上不必要的前缀

    @torch.no_grad()
    def normalize(self) -> None:
        self.wte.weight.data.copy_(normalize(self.wte.weight.data))
        self.lmhead.weight.data.copy_(normalize(self.lmhead.weight.data))
        for block in self.blocks:
            block.normalize()
        