"""train --force must rebuild even when the active model is still young."""

from __future__ import annotations

from nfl_oracle.recommendations.cli import _parser


def test_train_force_flag_defaults_false() -> None:
    args = _parser().parse_args(["train"])
    assert args.command == "train"
    assert args.force is False


def test_train_force_flag_true() -> None:
    args = _parser().parse_args(["train", "--force"])
    assert args.command == "train"
    assert args.force is True
