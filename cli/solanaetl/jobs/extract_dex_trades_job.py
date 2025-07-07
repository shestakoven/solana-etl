# The MIT License (MIT)
# Copyright (c) 2022 Gamejam.com
#
# Permission is hereby granted, free of charge, to any person obtaining a copy of this software
# and associated documentation files (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense,
# and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all copies or substantial
# portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED
# TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.


from blockchainetl_common.jobs.base_job import BaseJob
from blockchainetl_common.jobs.exporters.composite_item_exporter import \
    CompositeItemExporter
from solanaetl.executors.batch_work_executor import BatchWorkExecutor
from solanaetl.mappers.instruction_mapper import InstructionMapper
from solanaetl.mappers.dex_trade_mapper import DexTradeMapper
from solanaetl.providers.batch import BatchProvider
from solanaetl.services.dex_trade_extractor import \
    extract_dex_trade_from_instruction


class ExtractDexTradesJob(BaseJob):
    def __init__(
            self,
            instructions_iterable,
            batch_size,
            max_workers,
            item_exporter: CompositeItemExporter):
        self.instructions_iterable = instructions_iterable

        self.batch_work_executor = BatchWorkExecutor(batch_size, max_workers)
        self.item_exporter = item_exporter

        self.instruction_mapper = InstructionMapper()
        self.dex_trade_mapper = DexTradeMapper()

    def _start(self):
        self.item_exporter.open()

    def _export(self):
        self.batch_work_executor.execute(
            self.instructions_iterable, self._extract_dex_trades)

    def _extract_dex_trades(self, instruction_dicts):
        for instruction_dict in instruction_dicts:
            self._extract_dex_trade(instruction_dict)

    def _extract_dex_trade(self, instruction_dict):
        instruction = self.instruction_mapper.from_dict(
            instruction_dict)
        dex_trade = extract_dex_trade_from_instruction(
            instruction)
        if dex_trade is not None:
            self.item_exporter.export_item(
                self.dex_trade_mapper.to_dict(dex_trade))

    def _end(self):
        self.batch_work_executor.shutdown()
        self.item_exporter.close()