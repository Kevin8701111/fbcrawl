import scrapy
import logging
import os
from scrapy.loader import ItemLoader
from scrapy.http import FormRequest
from fbcrawl.items import FbcrawlItem
from dotenv import load_dotenv
load_dotenv()


class FacebookSpider(scrapy.Spider):
    """
    Parse FB pages (needs credentials)
    """    
    name = "fb"
    #name

    custom_settings = {
        'FEED_EXPORT_FIELDS': ['source','shared_from','date','text', 'texts', \
                               'reactions','likes','ahah','love','wow', \
                               'sigh','grrr','comments','url']
    }
    #輸出csv 欄位順序
        #current year, this variable is needed for parse_page recursion
    k = 2019
        #count number of posts, used to prioritized parsing and correctly insert in the csv
    count = 0
        #先寫入第幾行
    lang = 'it'    
    start_urls = ['https://mbasic.facebook.com']
        #預設網址之後會+上/@#$%^&*   

    def parse(self, response):
        '''
        Handle login with provided credentials
        '''
        email = os.getenv("EMAIL")
        password = os.getenv("PASSWORD")
        return FormRequest.from_response(
                response,
                formxpath='//form[contains(@action, "login")]',
                formdata={'email': email,'pass': password},
                callback=self.parse_home
        )
    #給formdata後給parse_home進行登入
  
    def parse_home(self, response):
        if response.xpath("//div/a[contains(@href,'save-device')]"):
            self.logger.info('Got stuck in "save-device" checkpoint')
            self.logger.info('I will now try to redirect to the correct page')
            return FormRequest.from_response(
                response,
                formdata={'name_action_selected': 'dont_save'},
                callback=self.parse_home
                )
    #     #登入後詢問的頁面 ,傳送拒絕    
        href = response.urljoin(self.page)
        # page = os.getenv("PAGE")                                                         
    #     #navigate to provided page
        # href = response.urljoin(page)
        print(href)
        return scrapy.Request(url=href,callback=self.parse_page,meta={'index':1})

    def parse_page(self, response):
        '''
        Parse the given page selecting the posts.
        Then ask recursively for another page.
        '''
        #select all posts
        posts = response.xpath("//div[contains(@data-ft,'top_level_post_id')]")
        posts = set(posts)
        for post in posts:            
            new = ItemLoader(item=FbcrawlItem(),selector=post)
            #加入方法並使用寫在item裡的方法做資料處理

            self.logger.info('Parsing post n = {}'.format(abs(self.count)))
            new.add_xpath('comments', "./div[2]/div[2]/a[1]/text()")

            #page_url #new.add_value('url',response.url)
            #returns full post-link in a list
            post = post.xpath(".//a[contains(@href,'footer')]/@href").extract()#.getdata
            new.add_value('url', "https://mbasic.facebook.com"+post[0])
            #直接寫入

            temp_post = response.urljoin(post[0])
            self.count -= 1
            yield scrapy.Request(temp_post, self.parse_post, priority = self.count, meta={'item':new})       

        #load following page
        #tries to click on "more", otherwise it looks for the appropriate
        #year for 1-click only and proceeds to click on others
        new_page = response.xpath("//div[2]/a[contains(@href,'timestart=') and not(contains(text(),'ent')) and not(contains(text(),number()))]/@href").extract()
        #換頁      
        if not new_page: 
            if response.meta['flag'] == self.k and self.k >= self.year:                
                self.logger.info('There are no more, flag set at = {}'.format(self.k))
                xpath = "//div/a[contains(@href,'time') and contains(text(),'" + str(self.k) + "')]/@href"
                new_page = response.xpath(xpath).extract()
                if new_page:
                    new_page = response.urljoin(new_page[0])
                    self.k -= 1
                    self.logger.info('Everything OK, new flag: {}'.format(self.k))                                
                    yield scrapy.Request(new_page, callback=self.parse_page, meta={'flag':self.k})
                else:
                    while not new_page: #sometimes the years are skipped 
                        self.logger.info('XPATH not found for year {}'.format(self.k-1))
                        self.k -= 1
                        self.logger.info('Trying with previous year, flag={}'.format(self.k))
                        if self.k < self.year:
                            self.logger.info('The previous year to crawl is less than the parameter year: {} < {}'.format(self.k,self.year))
                            self.logger.info('This is not handled well, please re-run with -a year="{}" or less'.format(self.k))
                            break                        
                        xpath = "//div/a[contains(@href,'time') and contains(text(),'" + str(self.k) + "')]/@href"
                        new_page = response.xpath(xpath).extract()
                    self.logger.info('New page found with flag {}'.format(self.k))
                    new_page = response.urljoin(new_page[0])
                    self.k -= 1
                    self.logger.info('Now going with flag {}'.format(self.k))
                    yield scrapy.Request(new_page, callback=self.parse_page, meta={'flag':self.k}) 
            else:
                self.logger.info('Crawling has finished with no errors!')
        else:
            new_page = response.urljoin(new_page[0])
            if 'flag' in response.meta:
                self.logger.info('Page scraped, click on more! flag = {}'.format(response.meta['flag']))
                yield scrapy.Request(new_page, callback=self.parse_page, meta={'flag':response.meta['flag']})
            else:
                self.logger.info('FLAG DOES NOT ALWAYS REPRESENT ACTUAL YEAR')
                self.logger.info('First page scraped, click on more! Flag not set, default flag = {}'.format(self.k))
                yield scrapy.Request(new_page, callback=self.parse_page, meta={'flag':self.k})
                
    def parse_post(self,response):
        with open ('comment_urls.csv','a+') as f :
            f.write(str(response.url)+'\n') 
        new = ItemLoader(item=FbcrawlItem(),response=response,parent=response.meta['item'])
        new.add_xpath('source', "//td/div/h3/strong/a/text() | //span/strong/a/text() | //div/div/div/a[contains(@href,'post_id')]/strong/text()")
        new.add_xpath('shared_from','//div[contains(@data-ft,"top_level_post_id") and contains(@data-ft,\'"isShare":1\')]/div/div[3]//strong/a/text()')
        new.add_xpath('date','//div/div/abbr/text()')
        content = response.xpath('//div[@data-ft]//p//text() | //div[@data-ft]/div[@class]/div[@class]/text()').extract()
        contents = []
        for c in range(0,len(content)):
            try:
                temp = content[c].replace(';',' ')
                contents.append(temp)
            except:
                temp = content[c]
                contents.append(temp)
        new.add_value('text',contents)
        new.add_xpath('reactions',"//a[contains(@href,'reaction/profile')]/div/div/text()")  
        
        reactions = response.xpath("//div[contains(@id,'sentence')]/a[contains(@href,'reaction/profile')]/@href")
        reactions = response.urljoin(reactions[0].extract())
        yield scrapy.Request(reactions, callback=self.parse_reactions, meta={'item':new})
        
    def parse_reactions(self,response):
        new = ItemLoader(item=FbcrawlItem(),response=response, parent=response.meta['item'])
        new.context['lang'] = self.lang
        new.add_xpath('likes',"//a[contains(@href,'reaction_type=1')]/span/text()")
        new.add_xpath('ahah',"//a[contains(@href,'reaction_type=4')]/span/text()")
        new.add_xpath('love',"//a[contains(@href,'reaction_type=2')]/span/text()")
        new.add_xpath('wow',"//a[contains(@href,'reaction_type=3')]/span/text()")
        new.add_xpath('sigh',"//a[contains(@href,'reaction_type=7')]/span/text()")
        new.add_xpath('grrr',"//a[contains(@href,'reaction_type=8')]/span/text()")
        yield new.load_item()