LONG_MOMENTUM_WINDOW = 30
SHORT_MOMENTUM_WINDOW = 10
REBALANCE_WINDOW = 1
BUY_LIMIT = 3
HOLD_LIMIT = 5
MIN_BUY_MOMENTUM = -8
MAX_SELL_MOMENTUM = -3
RESOLUTION = Resolution.Daily
CRYPTO_TICKERS = [
    "BTCUSD", "ETCUSD", "LTCUSD", "XRPUSD", "BCHUSD",
    "XLMUSD", "BSVUSD", "EOSUSD", "XMRUSD", "TRXUSD",
    "XTZUSD", "VETUSD"
]

class CryptoData:
    def __init__(self, symbol, algorithm):
        self.symbol = symbol
        self.algorithm = algorithm
        # 100 * (currentPrice - prevPrice) / prevPrice
        self.longMomentumPercent = algorithm.MOMP(symbol, LONG_MOMENTUM_WINDOW, RESOLUTION)
        self.shortMomentumPercent = algorithm.MOMP(symbol, SHORT_MOMENTUM_WINDOW, RESOLUTION)
    
    def isReady(self):
        '''Make sure that the data is available and the indicators are ready'''
        return (
            self.algorithm.Securities[self.symbol].HasData and
            self.longMomentumPercent.IsReady and
            self.shortMomentumPercent.IsReady
        )
    
    def isPotentialBuy(self):
        '''Buy if long momentum is higher than MIN_BUY_MOMENTUM'''
        self.algorithm.Log("Long momentum for {}: {}".format(self.symbol, self.longMomentumPercent))
        return self.longMomentumPercent.Current.Value >= MIN_BUY_MOMENTUM
    
    def isPotentialSell(self):
        '''Sell if short momentum is lower than MAX_SELL_MOMENTUM'''
        self.algorithm.Log("Short momentum for {}: {}".format(self.symbol, self.shortMomentumPercent))
        return self.shortMomentumPercent.Current.Value < MAX_SELL_MOMENTUM
    
    def __str__(self):
        return "{} price={} longMomp={} shortMomp={}".format(
            self.symbol,
            self.algorithm.Securities[self.symbol].Close,
            self.longMomentumPercent,
            self.shortMomentumPercent
        )

class TripleMomentum(QCAlgorithm):
    
    def Initialize(self):
        self.SetStartDate(2020, 1, 1)
        self.SetEndDate(2021, 1, 1)
        self.SetCash(10000)
        self.SetBrokerageModel(BrokerageName.Bitfinex, AccountType.Cash)
        self.cryptos = [CryptoData(self.AddCrypto(ticker, RESOLUTION).Symbol, self) for ticker in CRYPTO_TICKERS]
        self.prevRebalanceTime = datetime.min
    
    def OnData(self, data):
        if any([not crypto.isReady() for crypto in self.cryptos]):
            return
        if (self.Time - self.prevRebalanceTime).days < REBALANCE_WINDOW:
            return
        self.Log("===========================")
        self.Log(str(self.Portfolio.CashBook))
        self.prevRebalanceTime = self.Time
        if self.getAverageMomp() < 0:
            # The whole market is down - sell and wait
            for crypto in self.cryptos:
                self.Liquidate(crypto.symbol)
        else:
            sortedCryptos = sorted(self.cryptos, key = lambda c: c.longMomentumPercent, reverse = True)
            picksToBuy = [c for c in sortedCryptos[:BUY_LIMIT]]
            picksToKeep = [c for c in sortedCryptos[:HOLD_LIMIT]]
            sells = list(filter(lambda crypto: crypto not in picksToKeep or crypto.isPotentialSell(), self.cryptos))
            buys = list(filter(lambda crypto: crypto not in sells and crypto.isPotentialBuy(), picksToBuy))
            for crypto in sells:
                if self.Portfolio[crypto.symbol].Invested:
                    self.Log("Sell {}".format(crypto))
                    self.Liquidate(crypto.symbol)
            for crypto in buys:
                if not self.Portfolio[crypto.symbol].Invested:
                    self.Log("Buy {}".format(crypto))
                    self.SetHoldings(crypto.symbol, 0.9 / HOLD_LIMIT)
        self.Log(str(self.Portfolio.CashBook))
        
    def getAverageMomp(self):
        return sum([crypto.longMomentumPercent.Current.Value for crypto in self.cryptos]) / len(self.cryptos)
