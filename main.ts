import {createInterface} from 'node:readline';
import {pathToFileURL} from 'node:url';

// Causal long-only trend filter. No clocks, future bars, or external services.
export class Strategy {
  history=[]; fast=null; slow=null; peak=0; cooldown=0;
  step(price,cash,qty,depth,warmup=false){
    this.history.push(price);if(this.history.length>121)this.history.shift();
    this.fast=this.fast===null?price:this.fast+(price-this.fast)*2/17;
    this.slow=this.slow===null?price:this.slow+(price-this.slow)*2/81;
    if(warmup)return null;
    if(qty>0n){
      this.peak=Math.max(this.peak,price);
      if(price<this.peak*.994||(this.fast<this.slow&&price<this.slow)){
        this.cooldown=20;
        return {side:'sell',symbol:'CBBTC',qty,max_slippage_bps:150};
      }
      return null;
    }
    this.peak=price;
    if(this.cooldown>0){this.cooldown--;return null;}
    if(this.history.length<61)return null;
    const momentum=price/this.history.at(-61)-1;
    if(momentum>.003&&this.fast>this.slow*1.0005&&price>this.fast){
      const desired=cash*3n/4n, limit=depth/2000n;
      const amount=desired<limit?desired:limit;
      if(amount>=1000000n)return {side:'buy',symbol:'CBBTC',notional_quote_units:amount,max_slippage_bps:100};
    }
    return null;
  }
}

export async function run(){
  const bot=new Strategy();let warmup=0;
  for await(const line of createInterface({input:process.stdin,crlfDelay:Infinity})){
    if(!line.trim())continue;
    const msg=JSON.parse(line);
    if(msg.type==='hello')warmup=msg.warmup_bars??0;
    else if(msg.type==='batch'){
      const orders=[];
      for(const bar of msg.bars){
        if(bar.symbol!=='CBBTC')continue;
        const held=msg.account.positions.find(p=>p.symbol==='CBBTC');
        const depth=bar.c_depth.map(BigInt).reduce((a,b)=>a<b?a:b);
        const action=bot.step(Number(bar.c),BigInt(msg.account.cash_quote_units),BigInt(held?.qty??0),depth,msg.seq<warmup);
        if(action){action.client_id='t'+msg.seq;orders.push(action);}
      }
      process.stdout.write(JSON.stringify({type:'reply',seq:msg.seq,orders},(_,v)=>typeof v==='bigint'?v.toString():v)+'\n');
    }else if(msg.type==='done')return;
    else throw new Error('Unknown protocol message');
  }
}
if(process.argv[1]&&import.meta.url===pathToFileURL(process.argv[1]).href)await run();
