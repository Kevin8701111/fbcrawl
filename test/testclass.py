class Base(object):
    def __init__(self,a):
        print('data is: '+ str(a))
        self.a=a
    def printks(self):
        self.a = ['1','2','3']
        print(self.a)
        return self.a  
class MyBaseObject(Base):
    def __init__(self):
        # pass
        self.a=7
        super().__init__(6)

class MyObject(MyBaseObject):
    def __init__(self, game=None, *args,  **kwargs):
        super().__init__(*args, **kwargs)
        print('game is: ', game)

A = Base(5)
A.printk()
B = MyBaseObject()
B.printk()

