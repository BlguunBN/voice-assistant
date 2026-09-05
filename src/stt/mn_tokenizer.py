"""Tokenizer required by orgilj/moonshine-mn (adapted from its Apache-2.0 source)."""

from __future__ import annotations

import os
import shutil

import sentencepiece as spm
from transformers import PreTrainedTokenizer


class MnBPETokenizer(PreTrainedTokenizer):
    vocab_files_names = {"vocab_file": "mn_bpe.model"}
    model_input_names = ["input_ids", "attention_mask"]
    _special = {0: "<pad>", 1: "<s>", 2: "</s>"}
    _offset = 3

    def __init__(self, vocab_file: str, bos_token: str = "<s>", eos_token: str = "</s>", unk_token: str = "<unk>", pad_token: str = "</s>", **kwargs: object) -> None:
        self.sp_model = spm.SentencePieceProcessor()
        self.sp_model.Load(vocab_file)
        self.vocab_file = vocab_file
        super().__init__(bos_token=bos_token, eos_token=eos_token, unk_token=unk_token, pad_token=pad_token, **kwargs)

    @property
    def vocab_size(self) -> int:
        return self.sp_model.get_piece_size() + self._offset

    def get_vocab(self) -> dict[str, int]:
        return {self.convert_ids_to_tokens(index): index for index in range(self.vocab_size)}

    def _tokenize(self, text: str) -> list[str]:
        return self.sp_model.encode(text, out_type=str)

    def _convert_token_to_id(self, token: str) -> int:
        reverse = {value: key for key, value in self._special.items()}
        return reverse[token] if token in reverse else self.sp_model.piece_to_id(token) + self._offset

    def _convert_id_to_token(self, index: int) -> str:
        return self._special[index] if index in self._special else self.sp_model.id_to_piece(index - self._offset)

    def convert_tokens_to_string(self, tokens: list[str]) -> str:
        return self.sp_model.decode(tokens)

    def save_vocabulary(self, save_directory: str, filename_prefix: str | None = None) -> tuple[str, ...]:
        if not os.path.isdir(save_directory):
            return ()
        name = f"{filename_prefix + '-' if filename_prefix else ''}mn_bpe.model"
        output = os.path.join(save_directory, name)
        if os.path.abspath(self.vocab_file) != os.path.abspath(output):
            shutil.copyfile(self.vocab_file, output)
        return (output,)

    def decode_ids(self, ids: list[int]) -> str:
        pieces: list[int] = []
        for token_id in ids:
            if token_id == self.eos_token_id:
                break
            if token_id >= self._offset:
                pieces.append(token_id - self._offset)
        return self.sp_model.decode(pieces) if pieces else ""
